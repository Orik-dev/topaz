from arq import create_pool
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from aiogram import Bot
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


async def process_video_task(ctx: dict, task_id: int, user_telegram_id: int, video_file_id: str):
    """
    ARQ worker - обработка видео (POLLING!)
    """
    bot = Bot(token=settings.BOT_TOKEN)

    async with async_session_maker() as session:
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

            # Уведомляем пользователя
            await bot.send_message(
                chat_id=user.telegram_id,
                text="⏳ Обработка видео началась. Это может занять несколько минут..."
            )

            # Скачиваем видео
            file = await bot.get_file(video_file_id)
            video_data = await bot.download_file(file.file_path)
            video_bytes = video_data.read()

            # Парсим параметры
            params = json.loads(task.parameters) if task.parameters else {}
            
            # Получаем метаданные видео
            video_info = await bot.get_file(video_file_id)
            
            # Создаем запрос (Шаг 1)
            source = params.get("source", {})
            output = params.get("output", {})
            filters = params.get("filters", [])

            video_request = await topaz_client.create_video_request(
                source=source,
                output=output,
                filters=filters
            )

            request_id = video_request.get("requestId")
            task.topaz_request_id = request_id
            await session.flush()
            await session.commit()

            # Принимаем запрос (Шаг 2)
            accept_response = await topaz_client.accept_video_request(request_id)
            upload_urls = accept_response.get("uploadUrls", [])

            if not upload_urls:
                raise TopazAPIError("Не получены URL для загрузки")

            # Загружаем видео (Шаг 3)
            upload_url = upload_urls[0].get("url")
            etag = await topaz_client.upload_video(upload_url, video_bytes)

            # Завершаем загрузку (Шаг 4)
            await topaz_client.complete_video_upload(
                request_id=request_id,
                upload_results=[{"partNum": 1, "eTag": etag}]
            )

            # POLLING статуса (НЕТ вебхуков в Topaz!)
            max_attempts = 360  # 1 час (каждые 10 сек)
            for attempt in range(max_attempts):
                await asyncio.sleep(10)

                status = await topaz_client.get_video_status(request_id)
                state = status.get("state")

                if state == "completed":
                    download_url = status.get("downloadUrl")
                    task.output_file_url = download_url

                    # Списываем генерации ТОЛЬКО после успеха
                    success = await UserService.deduct_credits(
                        session=session,
                        user=user,
                        amount=task.cost,
                        description=f"Улучшение видео",
                        reference_type="task",
                        reference_id=task.id
                    )

                    if not success:
                        task.status = TaskStatus.FAILED
                        task.error_message = "Недостаточно генераций"
                        await session.flush()
                        await session.commit()
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text="❌ Недостаточно генераций"
                        )
                        return

                    task.status = TaskStatus.COMPLETED
                    await session.flush()
                    await session.commit()

                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"✅ Видео улучшено!\n\n"
                             f"📥 [Скачать видео]({download_url})\n\n"
                             f"💰 Списано: {int(task.cost)} ген.\n"
                             f"⚡ Баланс: {int(user.balance)} ген.",
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )

                    logger.info(f"Video task {task_id} completed")
                    return

                elif state == "failed":
                    raise TopazAPIError("Обработка видео не удалась")

                # Прогресс
                if attempt % 6 == 0:  # Каждую минуту
                    progress = status.get("progress", 0)
                    logger.info(f"Video task {task_id} progress: {progress}%")

            # Timeout
            raise TopazAPIError("Превышено время обработки видео")

        except TopazAPIError as e:
            logger.error(f"Topaz API error in video task {task_id}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
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

            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"❌ {str(e)}\n\n💰 Возврат: {int(task.cost)} ген.\n⚡ Баланс: {int(user.balance)} ген."
            )

        except Exception as e:
            logger.error(f"Unexpected error in video task {task_id}: {e}", exc_info=True)
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

            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"❌ Произошла ошибка\n\n💰 Возврат: {int(task.cost)} ген.\n⚡ Баланс: {int(user.balance)} ген."
            )

        finally:
            await bot.session.close()


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_video_task]
    redis_settings = get_redis_settings()
    max_jobs = 3  # Меньше для видео
    job_timeout = 3600  # 1 час
    keep_result = 3600