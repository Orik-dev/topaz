import asyncio
import os
import signal
import sys
import logging
import json
from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from src.services.telegram_safe import safe_send_video, safe_send_text, safe_edit_text
from src.utils.file_manager import disk_manager, DiskManager
from src.utils.file_validator import file_validator
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_shutdown_flag = False


def signal_handler(signum, frame):
    global _shutdown_flag
    logger.warning(f"Received signal {signum}, graceful shutdown...")
    _shutdown_flag = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


async def _safe_refund(session: AsyncSession, user: User, task: Task, reason: str):
    """Безопасный возврат генераций"""
    try:
        if task.status != TaskStatus.FAILED:
            return
        
        await UserService.add_credits(
            session=session,
            user=user,
            amount=task.cost,
            description=f"Возврат: {reason}",
            reference_type="refund",
            reference_id=task.id
        )
        await session.commit()
        logger.info(f"Refund success: task={task.id}, amount={task.cost}, reason={reason}")
    except Exception as e:
        logger.error(f"Refund error: task={task.id}, error={e}")


async def _check_cancel_flag(task_id: int) -> bool:
    """Проверка флага отмены"""
    try:
        redis = await aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_CACHE
        )
        cancel_flag = await redis.get(f"cancel_task:{task_id}")
        await redis.aclose()
        return cancel_flag is not None
    except Exception as e:
        logger.error(f"Check cancel error: {e}")
        return False


async def process_video_task(ctx: dict, task_id: int, user_telegram_id: int, video_file_id: str):
    global _shutdown_flag
    
    if _shutdown_flag:
        logger.warning(f"Shutdown in progress, skipping task {task_id}")
        return
    
    bot = Bot(token=settings.BOT_TOKEN)
    temp_input = None
    temp_output = None
    request_id = None
    progress_message = None

    async with async_session_maker() as session:
        try:
            # Проверка диска
            if not DiskManager.check_disk_space():
                await safe_send_text(
                    bot,
                    user_telegram_id,
                    "⚠️ <b>Сервер перегружен</b>\n\nПопробуйте через 5-10 минут",
                    parse_mode="HTML"
                )
                return
            
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

            # Клавиатура с отменой
            cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_task:{task_id}")]
            ])
            
            progress_message = await bot.send_message(
                user_telegram_id,
                "⏳ <b>Загружаю видео...</b>\n\n"
                "Это может занять 1-2 минуты",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )

            # Скачиваем видео
            file = await bot.get_file(video_file_id)
            
            # Проверка размера ДО скачивания
            valid, error_msg = file_validator.validate_video_size(file.file_size)
            if not valid:
                raise TopazAPIError("File too large", user_message=error_msg)
            
            video_data = await bot.download_file(file.file_path)
            video_bytes = video_data.read()
            
            temp_input = disk_manager.save_temp_file(video_bytes, '.mp4')
            file_size = os.path.getsize(temp_input)
            
            logger.info(f"Video downloaded: size={file_size}, task={task_id}")

            # Обновление прогресса
            await safe_edit_text(
                progress_message,
                "📤 <b>Загружаю на сервер обработки...</b>\n\n"
                "Подготовка видео...",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )

            params = json.loads(task.parameters) if task.parameters else {}
            
            # Шаг 1: Создать запрос
            source = params.get("source", {})
            source["size"] = file_size
            
            output = params.get("output", {})
            filters = params.get("filters", [])
            
            create_resp = await topaz_client.create_video_request(
                source=source,
                filters=filters,
                output=output
            )
            request_id = create_resp["requestId"]
            task.topaz_request_id = request_id
            await session.flush()
            await session.commit()
            
            logger.info(f"Video request created: {request_id}, task={task_id}")

            # Шаг 2: Accept
            accept_resp = await topaz_client.accept_video_request(request_id)
            upload_urls = accept_resp.get("uploadUrls", [])
            if not upload_urls:
                raise TopazAPIError("No upload URLs", user_message="Не получены ссылки для загрузки")

            # Проверка отмены
            if await _check_cancel_flag(task_id):
                raise TopazAPIError("Canceled by user", user_message="Отменено пользователем")

            # Шаг 3: Upload
            etag = await topaz_client.upload_video_to_url(upload_urls[0], video_bytes)
            logger.info(f"Video uploaded: etag={etag}, task={task_id}")
            
            # Шаг 4: Complete
            await topaz_client.complete_video_upload(request_id, [{"partNum": 1, "eTag": etag}])
            
            await safe_edit_text(
                progress_message,
                "🎬 <b>Обработка началась!</b>\n\n"
                "⏳ Это займет несколько минут...\n"
                "📊 Прогресс: 0%",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
            
            logger.info(f"Video processing started: request={request_id}")

            # Шаг 5: Polling
            download_url = None
            last_progress = -1
            
            for i in range(360):  # 1 час
                await asyncio.sleep(10)
                
                # Проверка отмены
                if await _check_cancel_flag(task_id):
                    logger.info(f"User canceled task: {task_id}")
                    await topaz_client.cancel_video_request(request_id)
                    raise TopazAPIError("Canceled by user", user_message="Отменено пользователем")
                
                # Проверка shutdown
                if _shutdown_flag:
                    logger.warning(f"Shutdown during processing: task={task_id}")
                    break
                
                try:
                    status_data = await topaz_client.get_video_status(request_id)
                except TopazAPIError as e:
                    logger.warning(f"Status check error: {e}")
                    continue
                
                status = status_data.get("status", "").lower()
                progress = status_data.get("progress", 0)
                
                # Обновление прогресса каждые 30 секунд
                if i % 3 == 0 and progress != last_progress and progress_message:
                    try:
                        progress_bar = "▰" * (progress // 10) + "▱" * (10 - progress // 10)
                        await safe_edit_text(
                            progress_message,
                            f"🎬 <b>Обработка видео...</b>\n\n"
                            f"{progress_bar} {progress}%\n\n"
                            f"⏱ Осталось примерно {(100 - progress) // 10} мин",
                            reply_markup=cancel_kb,
                            parse_mode="HTML"
                        )
                        last_progress = progress
                    except Exception:
                        pass
                
                # Обработка статусов
                if status == "complete":
                    download_url = status_data.get("download", {}).get("url")
                    if download_url:
                        logger.info(f"Video complete: task={task_id}")
                        break
                    else:
                        raise TopazAPIError("No download URL", user_message="Не получена ссылка на результат")
                
                elif status == "failed":
                    error_msg = status_data.get("message", "Processing failed")
                    logger.error(f"Video processing failed: {error_msg}, task={task_id}")
                    raise TopazAPIError(f"Processing failed: {error_msg}", user_message="Обработка не удалась")
                
                elif status in ["canceled", "cancelled"]:
                    raise TopazAPIError("Processing canceled", user_message="Обработка отменена")
                
                elif status == "canceling":
                    raise TopazAPIError("Processing being canceled", user_message="Обработка отменяется")
            
            if not download_url:
                logger.error(f"Video processing timeout: task={task_id}")
                try:
                    await topaz_client.cancel_video_request(request_id)
                except Exception as e:
                    logger.error(f"Cancel after timeout failed: {e}")
                raise TopazAPIError("Processing timeout", user_message="Превышено время обработки (1 час)")

            # Шаг 6: Download
            await safe_edit_text(
                progress_message,
                "⬇️ <b>Скачиваю результат...</b>\n\n"
                "Почти готово!",
                parse_mode="HTML"
            )
            
            try:
                async with topaz_client._get_session() as session_dl:
                    async with session_dl.get(download_url) as resp:
                        if resp.status == 200:
                            result_data = await resp.read()
                        else:
                            raise TopazAPIError("Download failed", user_message="Ошибка скачивания результата")
            except Exception as e:
                logger.error(f"Download error: {e}, task={task_id}")
                raise TopazAPIError(f"Download error: {e}", user_message="Ошибка скачивания результата")

            temp_output = disk_manager.save_temp_file(result_data, '.mp4')
            logger.info(f"Video downloaded: size={len(result_data)}, task={task_id}")

            # Списание генераций
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Обработка видео: {task.model}",
                reference_type="task",
                reference_id=task.id
            )
            
            if not success:
                raise TopazAPIError("Insufficient balance", user_message="Недостаточно генераций")

            # Отправка результата
            video_file = FSInputFile(temp_output)
            await safe_send_video(
                bot=bot,
                chat_id=user.telegram_id,
                video=video_file,
                caption=(
                    f"✅ <b>Видео готово!</b>\n\n"
                    f"💰 Списано: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                ),
                parse_mode="HTML"
            )

            task.status = TaskStatus.COMPLETED
            await session.flush()
            await session.commit()
            
            logger.info(f"Video task completed: task={task_id}")

        except TopazAPIError as e:
            logger.error(f"Topaz API error: {e}, task={task_id}")
            
            if request_id:
                try:
                    await topaz_client.cancel_video_request(request_id)
                except Exception as cancel_error:
                    logger.error(f"Cancel request failed: {cancel_error}")
            
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await session.flush()
            await session.commit()

            await _safe_refund(session, user, task, e.user_message or str(e))

            user_msg = e.user_message or "Ошибка обработки видео"
            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ <b>{user_msg}</b>\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген.\n\n"
                    f"Попробуйте другое видео или напишите в поддержку."
                ),
                parse_mode="HTML"
            )

        except Exception as e:
            logger.exception(f"Unexpected error: task={task_id}, error={e}")
            
            task.status = TaskStatus.FAILED
            task.error_message = f"Internal error: {str(e)}"
            await session.flush()
            await session.commit()

            await _safe_refund(session, user, task, "Внутренняя ошибка")

            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ <b>Произошла ошибка обработки</b>\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген.\n\n"
                    f"Попробуйте позже или напишите в поддержку."
                ),
                parse_mode="HTML"
            )

        finally:
            disk_manager.cleanup_file(temp_input)
            disk_manager.cleanup_file(temp_output)
            await bot.session.close()


async def startup(ctx):
    logger.info("✅ Video worker started")


async def shutdown(ctx):
    await topaz_client.close()
    logger.info("🛑 Video worker stopped")


class WorkerSettings:
    functions = [process_video_task]
    redis_settings = get_redis_settings()
    max_jobs = 3
    job_timeout = 7200
    keep_result = 3600
    on_startup = startup
    on_shutdown = shutdown