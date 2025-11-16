from arq import create_pool
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from aiogram import Bot
from aiogram.types import BufferedInputFile
import logging
import json

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

            # Вызываем Topaz API (СИНХРОННЫЙ!)
            result_data = await topaz_client.enhance_image(
                image_data=image_data,
                model=task.model,
                **params
            )

            # Списываем генерации ТОЛЬКО после успеха
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Улучшение фото",
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
                caption=f"✅ Фото улучшено!\n\n💰 Списано: {int(task.cost)} ген.\n⚡ Баланс: {int(user.balance)} ген."
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


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_image_task]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 600  # 10 минут
    keep_result = 3600