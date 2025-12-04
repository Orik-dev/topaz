from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from aiogram import Bot
from src.db.engine import async_session_maker
from src.db.models import User
from src.services.users import UserService
from src.services.telegram_safe import safe_send_text
from src.services.payments import PaymentService
from sqlalchemy import select
import redis.asyncio as aioredis
from src.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """
    ✅ Webhook от YooKassa с идемпотентностью
    """
    try:
        payload = await request.json()
        event = payload.get("event")
        
        logger.info(f"YooKassa webhook: event={event}")
        
        if event != "payment.succeeded":
            return JSONResponse({"ok": True})
        
        payment_obj = payload.get("object", {})
        payment_id = payment_obj.get("id")
        
        # ✅ Идемпотентность через Redis
        redis = await aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_CACHE
        )
        idempotency_key = f"yookassa:processed:{payment_id}"
        
        try:
            already_processed = await redis.exists(idempotency_key)
            if already_processed:
                logger.warning(f"Payment already processed: {payment_id}")
                return JSONResponse({"ok": True})
            
            await redis.setex(idempotency_key, 86400 * 7, "1")
        finally:
            await redis.aclose()
        
        # Получаем metadata
        metadata = payment_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        credits = metadata.get("credits")
        
        if not user_id or not credits:
            logger.error(f"Invalid metadata: user_id={user_id}, credits={credits}")
            return JSONResponse({"status": "error", "message": "Invalid metadata"})
        
        # Зачисляем генерации
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.id == int(user_id))
            )
            user = result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User not found: user_id={user_id}")
                return JSONResponse({"status": "error", "message": "User not found"})
            
            await UserService.add_credits(
                session=session,
                user=user,
                amount=float(credits),
                description=f"Пополнение YooKassa: {payment_id}",
                reference_type="payment_yookassa"
            )
            await session.commit()
            
            logger.info(f"YooKassa payment processed: user_id={user_id}, credits={credits}")
            
            # Уведомление пользователю
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await safe_send_text(
                        bot=bot,
                        chat_id=user.telegram_id,
                        text=(
                            f"✅ <b>Оплата успешна!</b>\n\n"
                            f"💰 Начислено: {int(float(credits))} ген.\n"
                            f"⚡ Баланс: {int(user.balance)} ген.\n\n"
                            f"Используйте /start для начала работы"
                        ),
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
            finally:
                await bot.session.close()
        
        return JSONResponse({"ok": True})
        
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")