import asyncio
from arq import create_pool
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from src.services.pricing import VIDEO_MODELS
from src.services.telegram_safe import safe_send_video, safe_send_text
from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile
import logging
import json
import tempfile
import os

logger = logging.getLogger(__name__)


async def process_video_task(ctx: dict, task_id: int, user_telegram_id: int, video_file_id: str):
    """ARQ worker - обработка видео"""
    bot = Bot(token=settings.BOT_TOKEN)

    async with async_session_maker() as session:
        temp_input_path = None
        temp_output_path = None
        
        try:
            task = await session.get(Task, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            user = await session.get(User, task.user_id)
            if not user:
                logger.error(f"User {task.user_id} not found")
                return

            task.status = TaskStatus.PROCESSING
            await session.flush()
            await session.commit()

            # Отправляем уведомление о начале обработки
            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text="⏳ Начинаю обработку видео... Это может занять несколько минут."
            )

            # Скачиваем видео во временный файл
            file = await bot.get_file(video_file_id)
            video_data = await bot.download_file(file.file_path)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(video_data.read())
                temp_input_path = tmp.name
            
            video_size = os.path.getsize(temp_input_path)
            logger.info(f"Downloaded video: size={video_size} bytes, path={temp_input_path}")

            # Парсим параметры
            params = json.loads(task.parameters) if task.parameters else {}
            model_info = VIDEO_MODELS.get(task.model, {})
            
            # Создаем запрос на обработку видео
            video_request = await topaz_client.create_video_request(
                source_resolution=params.get("source_resolution", {"width": 1280, "height": 720}),
                source_container=params.get("source_container", "mp4"),
                source_size=video_size,
                source_duration=params.get("source_duration", 10000),
                source_frame_rate=params.get("source_frame_rate", 30),
                source_frame_count=params.get("source_frame_count", 300),
                output_resolution=params.get("output_resolution", {"width": 1920, "height": 1080}),
                output_frame_rate=params.get("output_frame_rate", 60),
                filters=params.get("filters", [
                    {
                        "model": params.get("model", "prob-4"),
                        "videoType": "Progressive",
                        "auto": "Relative"
                    }
                ])
            )
            
            request_id = video_request.get("requestId")
            estimated_cost = video_request.get("estimatedCost", 0)
            
            logger.info(f"Video request created: request_id={request_id}, cost={estimated_cost}")
            
            # Принимаем запрос и получаем upload URLs
            accept_response = await topaz_client.accept_video_request(request_id)
            upload_urls = accept_response.get("uploadUrls", [])
            
            if not upload_urls:
                raise TopazAPIError("Не получены URL для загрузки видео")
            
            # Загружаем видео
            logger.info(f"Uploading video to {len(upload_urls)} URLs")
            
            with open(temp_input_path, 'rb') as video_file:
                video_bytes = video_file.read()
            
            upload_results = []
            
            if len(upload_urls) == 1:
                # Загружаем целиком
                etag = await topaz_client.upload_video_part(
                    upload_url=upload_urls[0],
                    video_data=video_bytes
                )
                upload_results.append({"partNum": 1, "eTag": etag})
            else:
                # Загружаем частями
                chunk_size = len(video_bytes) // len(upload_urls)
                for i, url in enumerate(upload_urls):
                    start = i * chunk_size
                    end = start + chunk_size if i < len(upload_urls) - 1 else len(video_bytes)
                    chunk = video_bytes[start:end]
                    
                    etag = await topaz_client.upload_video_part(
                        upload_url=url,
                        video_data=chunk
                    )
                    upload_results.append({"partNum": i + 1, "eTag": etag})
            
            logger.info(f"Video uploaded successfully: {len(upload_results)} parts")
            
            # Завершаем загрузку
            await topaz_client.complete_video_upload(request_id, upload_results)
            
            logger.info(f"Video upload completed, starting processing")
            
            # Polling статуса обработки
            result_url = await _poll_video_status(request_id)
            
            # Скачиваем результат
            result_data = await topaz_client.download_video_output(result_url)
            
            # Сохраняем результат во временный файл
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                tmp.write(result_data)
                temp_output_path = tmp.name
            
            logger.info(f"Video processed successfully: output_path={temp_output_path}")
            
            # Списываем генерации ТОЛЬКО после успешной обработки
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Обработка видео: {model_info.get('description', 'Unknown')}",
                reference_type="task",
                reference_id=task.id
            )

            if not success:
                task.status = TaskStatus.FAILED
                task.error_message = "Недостаточно генераций"
                await session.flush()
                await session.commit()
                
                await safe_send_text(
                    bot=bot,
                    chat_id=user.telegram_id,
                    text="❌ Недостаточно генераций"
                )
                return

            # Отправляем результат
            video_file = FSInputFile(temp_output_path)
            await safe_send_video(
                bot=bot,
                chat_id=user.telegram_id,
                video=video_file,
                caption=(
                    f"✅ {model_info.get('description', 'Видео улучшено')}!\n\n"
                    f"💰 Списано: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                )
            )

            task.status = TaskStatus.COMPLETED
            await session.flush()
            await session.commit()

            logger.info(f"Video task {task_id} completed successfully")

        except TopazAPIError as e:
            logger.error(f"Topaz API error in task {task_id}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await session.flush()
            await session.commit()

            # Возврат генераций
            await UserService.add_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Возврат за ошибку: {str(e)}",
                reference_type="refund",
                reference_id=task.id
            )
            await session.commit()

            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ Ошибка обработки видео: {str(e)}\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                )
            )

        except Exception as e:
            logger.error(f"Unexpected error in task {task_id}: {e}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error_message = "Внутренняя ошибка"
            await session.flush()
            await session.commit()

            # Возврат генераций
            await UserService.add_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Возврат за ошибку",
                reference_type="refund",
                reference_id=task.id
            )
            await session.commit()

            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ Произошла ошибка обработки видео\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                )
            )

        finally:
            # Очищаем временные файлы
            if temp_input_path and os.path.exists(temp_input_path):
                try:
                    os.unlink(temp_input_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp input file: {e}")
            
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.unlink(temp_output_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp output file: {e}")
            
            await bot.session.close()


async def _poll_video_status(request_id: str) -> str:
    """Polling статуса обработки видео и получение URL результата"""
    max_attempts = 360  # 60 минут (360 * 10 секунд)
    
    for attempt in range(max_attempts):
        await asyncio.sleep(10)
        
        try:
            status_data = await topaz_client.get_video_status(request_id)
            status = status_data.get("status", "").lower()
            progress = status_data.get("progress", 0)
            
            logger.info(
                f"Polling video status: request_id={request_id}, "
                f"attempt={attempt}, status={status}, progress={progress}%"
            )
            
            if status == "completed" or status == "complete":
                download_url = status_data.get("downloadUrl") or status_data.get("outputUrl")
                if not download_url:
                    raise TopazAPIError("Не получен URL для скачивания результата")
                return download_url
                
            elif status == "failed":
                error_msg = status_data.get("error", "Обработка не удалась")
                raise TopazAPIError(f"Обработка не удалась: {error_msg}")
            
            elif status == "cancelled" or status == "canceled":
                raise TopazAPIError("Обработка отменена")
            
            elif status in ["queued", "processing", "uploading"]:
                # Продолжаем ожидание
                continue
            else:
                logger.warning(f"Unknown status: {status}")
                continue
        
        except TopazAPIError:
            raise
        except Exception as e:
            logger.warning(f"Polling error: {e}")
            continue
    
    raise TopazAPIError("Превышено время обработки видео (60 минут)")


# ✅ ИСПРАВЛЕНИЕ - добавляем startup/shutdown функции
async def startup(ctx):
    """Инициализация worker при запуске"""
    logger.info("🚀 Video worker started successfully")


async def shutdown(ctx):
    """Очистка при остановке worker"""
    logger.info("🛑 Video worker shutting down")


class WorkerSettings:
    """ARQ worker configuration с правильной инициализацией"""
    functions = [process_video_task]
    redis_settings = get_redis_settings()
    max_jobs = 5  # Меньше параллельных задач для видео
    job_timeout = 7200  # 2 часа на обработку видео
    keep_result = 7200
    on_startup = startup      # ✅ ДОБАВЛЕНО
    on_shutdown = shutdown    # ✅ ДОБАВЛЕНО