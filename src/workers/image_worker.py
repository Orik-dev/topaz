import logging
import json
from aiogram import Bot
from aiogram.types import BufferedInputFile
from src.db.engine import async_session_maker
from src.db.models import Task, TaskStatus, User
from src.vendors.topaz import topaz_client, TopazAPIError
from src.services.users import UserService
from src.core.config import settings
from src.workers.settings import get_redis_settings
from src.services.telegram_safe import safe_send_photo, safe_send_text
from src.utils.file_manager import disk_manager, DiskManager

logger = logging.getLogger(__name__)


async def _safe_refund(session, user, task, reason):
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
        logger.info(f"Refund success: task={task.id}, amount={task.cost}")
    except Exception as e:
        logger.error(f"Refund error: task={task.id}, error={e}")


async def process_image_task(ctx: dict, task_id: int, user_telegram_id: int, image_file_id: str):
    bot = Bot(token=settings.BOT_TOKEN)

    async with async_session_maker() as session:
        try:
            # Проверка диска
            if not DiskManager.check_disk_space():
                await safe_send_text(
                    bot,
                    user_telegram_id,
                    "⚠️ Сервер перегружен, попробуйте через 5 минут"
                )
                return
            
            task = await session.get(Task, task_id)
            if not task:
                return
            user = await session.get(User, task.user_id)
            if not user:
                return

            task.status = TaskStatus.PROCESSING
            await session.flush()
            await session.commit()

            file = await bot.get_file(image_file_id)
            image_data = await bot.download_file(file.file_path)
            image_bytes = image_data.read()

            params = json.loads(task.parameters) if task.parameters else {}
            endpoint = params.get("endpoint", "enhance")

            logger.info(f"Processing image: task={task_id}, endpoint={endpoint}, model={task.model}")

            if endpoint == "enhance":
                result = await topaz_client.enhance_image(image_bytes, **params)
            elif endpoint == "sharpen":
                result = await topaz_client.sharpen_image(image_bytes, **params)
            elif endpoint == "denoise":
                result = await topaz_client.denoise_image(image_bytes, **params)
            else:
                raise ValueError(f"Unknown endpoint: {endpoint}")

            logger.info(f"Image processed: task={task_id}, size={len(result)}")

            # Списание
            success = await UserService.deduct_credits(
                session=session,
                user=user,
                amount=task.cost,
                description=f"Обработка фото: {task.model}",
                reference_type="task",
                reference_id=task.id
            )
            
            if not success:
                raise TopazAPIError("Insufficient balance", user_message="Недостаточно генераций")

            img_file = BufferedInputFile(result, filename="result.jpg")
            await safe_send_photo(
                bot=bot,
                chat_id=user.telegram_id,
                photo=img_file,
                caption=(
                    f"✅ <b>Фото готово!</b>\n\n"
                    f"💰 Списано: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
                ),
                parse_mode="HTML"
            )

            task.status = TaskStatus.COMPLETED
            await session.flush()
            await session.commit()
            
            logger.info(f"Image task completed: task={task_id}")

        except TopazAPIError as e:
            logger.error(f"Topaz API error: {e}, task={task_id}")
            
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            await session.flush()
            await session.commit()

            await _safe_refund(session, user, task, e.user_message or str(e))

            user_msg = e.user_message or "Ошибка обработки фото"
            await safe_send_text(
                bot=bot,
                chat_id=user.telegram_id,
                text=(
                    f"❌ <b>{user_msg}</b>\n\n"
                    f"💰 Возврат: {int(task.cost)} ген.\n"
                    f"⚡ Баланс: {int(user.balance)} ген."
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
                    f"⚡ Баланс: {int(user.balance)} ген."
                ),
                parse_mode="HTML"
            )

        finally:
            await bot.session.close()


async def startup(ctx):
    logger.info("✅ Image worker started")


async def shutdown(ctx):
    await topaz_client.close()
    logger.info("🛑 Image worker stopped")


class WorkerSettings:
    functions = [process_image_task]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 3600
    keep_result = 3600
    on_startup = startup
    on_shutdown = shutdown