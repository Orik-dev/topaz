from arq import create_pool
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from src.services.pricing import IMAGE_MODELS
from aiogram import Bot
from aiogram.types import BufferedInputFile
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


async def process_image_task(ctx: dict, task_id: int, user_telegram_id: int, image_data: bytes):
    """
    ARQ worker - обработка фото
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

            # Обновляем статус
            task.status = TaskStatus.PROCESSING
            await session.flush()
            await session.commit()

            # Парсим параметры
            params = json.loads(task.parameters) if task.parameters else {}
            endpoint = params.pop("endpoint", "enhance")
            
            # Получаем модель
            model_info = IMAGE_MODELS.get(task.model)
            if not model_info:
                raise ValueError(f"Unknown model: {task.model}")

            # Вызываем нужный endpoint
            result_data = None
            
            if endpoint == "enhance":
                # Синхронный endpoint
                result_data = await topaz_client.enhance_image(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                
            elif endpoint == "sharpen":
                # Синхронный endpoint
                result_data = await topaz_client.sharpen_image(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                
            elif endpoint == "denoise":
                # Синхронный endpoint
                result_data = await topaz_client.denoise_image(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                
            elif endpoint == "enhance-gen/async":
                # Асинхронный endpoint - требует polling
                process_id = await topaz_client.enhance_image_async(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                result_data = await _poll_and_download_image(process_id)
                
            elif endpoint == "sharpen-gen/async":
                # Асинхронный endpoint - требует polling
                process_id = await topaz_client.sharpen_image_async(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                result_data = await _poll_and_download_image(process_id)
                
            elif endpoint == "restore-gen/async":
                # Асинхронный endpoint - требует polling
                process_id = await topaz_client.restore_image_async(
                    image_data=image_data,
                    model=task.model,
                    **params
                )
                result_data = await _poll_and_download_image(process_id)
            
            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")

            # Списываем генерации ТОЛЬКО после успеха
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Обработка фото: {model_info['description']}",
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

            # Отправляем результат
            input_file = BufferedInputFile(result_data, filename="enhanced.jpg")
            await bot.send_photo(
                chat_id=user.telegram_id,
                photo=input_file,
                caption=f"✅ {model_info['description']}\n\n💰 Списано: {int(task.cost)} ген.\n⚡ Баланс: {int(user.balance)} ген."
            )

            task.status = TaskStatus.COMPLETED
            await session.flush()
            await session.commit()

            logger.info(f"Image task {task_id} completed")

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

            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"❌ Произошла ошибка\n\n💰 Возврат: {int(task.cost)} ген.\n⚡ Баланс: {int(user.balance)} ген."
            )

        finally:
            await bot.session.close()


async def _poll_and_download_image(process_id: str) -> bytes:
    """
    Polling статуса и скачивание результата для async endpoint'ов
    """
    max_attempts = 180  # 30 минут (каждые 10 сек)
    
    for attempt in range(max_attempts):
        await asyncio.sleep(10)
        
        status_data = await topaz_client.get_image_status(process_id)
        status = status_data.get("status")
        
        if status == "Completed":
            # Скачиваем результат
            return await topaz_client.download_image_output(process_id)
            
        elif status == "Failed":
            raise TopazAPIError("Обработка не удалась")
        
        elif status == "Cancelled":
            raise TopazAPIError("Обработка отменена")
    
    # Timeout
    raise TopazAPIError("Превышено время обработки")


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_image_task]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 3600  # 1 час для generative моделей
    keep_result = 3600