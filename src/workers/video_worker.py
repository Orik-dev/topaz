import asyncio
from arq import create_pool
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from src.services.pricing import IMAGE_MODELS
from src.services.telegram_safe import safe_send_photo, safe_send_text
from aiogram import Bot
from aiogram.types import BufferedInputFile
import logging
import json

logger = logging.getLogger(__name__)


async def process_image_task(ctx: dict, task_id: int, user_telegram_id: int, image_file_id: str):
    """ARQ worker - обработка изображения"""
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

            # Скачиваем фото
            file = await bot.get_file(image_file_id)
            image_data = await bot.download_file(file.file_path)
            image_bytes = image_data.read()

            # Парсим параметры
            params = json.loads(task.parameters) if task.parameters else {}
            model_info = IMAGE_MODELS.get(task.model, {})
            endpoint = params.get("endpoint", "enhance")

            # Вызываем нужный endpoint
            result_data = None
            
            if endpoint == "enhance":
                result_data = await topaz_client.enhance_image(
                    image_data=image_bytes,
                    model=params.get("model", "Standard V2"),
                    output_width=params.get("output_width", 3840),
                    face_enhancement=params.get("face_enhancement", True),
                    face_enhancement_strength=params.get("face_enhancement_strength", 0.8)
                )
            
            # Списываем генерации
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Обработка фото: {model_info.get('description', 'Unknown')}",
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
            input_file = BufferedInputFile(result_data, filename="enhanced.jpg")
            await safe_send_photo(
                bot=bot,
                chat_id=user.telegram_id,
                photo=input_file,
                caption=(
                    f"✅ {model_info.get('description', 'Фото улучшено')}!\n\n"
                    f"💰 Списано: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                )
            )

            task.status = TaskStatus.COMPLETED
            await session.flush()
            await session.commit()

            logger.info(f"Image task {task_id} completed successfully")

        except Exception as e:
            logger.error(f"Error in task {task_id}: {e}", exc_info=True)
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

            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ Произошла ошибка обработки\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                )
            )

        finally:
            await bot.session.close()


class WorkerSettings:
    """ARQ worker configuration"""
    functions = [process_image_task]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 3600
    keep_result = 3600