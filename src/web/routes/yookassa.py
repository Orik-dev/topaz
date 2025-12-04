from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from yookassa import Payment
from src.db.engine import async_session_maker
from src.db.models import User
from src.services.users import UserService
from sqlalchemy import select
import redis.asyncio as aioredis
from src.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/yookassa/callback")
async def yookassa_callback(request: Request):
    try:
        body = await request.json()
        event = body.get("event")
        
        logger.info(f"YooKassa webhook: event={event}")
        
        if event != "payment.succeeded":
            return JSONResponse({"status": "ok"})
        
        payment_obj = body.get("object", {})
        payment_id = payment_obj.get("id")
        
        # Идемпотентность
        redis = await aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_CACHE
        )
        idempotency_key = f"yookassa:processed:{payment_id}"
        
        already_processed = await redis.exists(idempotency_key)
        if already_processed:
            logger.warning(f"Payment already processed: {payment_id}")
            await redis.aclose()
            return JSONResponse({"status": "ok"})
        
        await redis.setex(idempotency_key, 86400 * 7, "1")
        await redis.aclose()
        
        metadata = payment_obj.get("metadata", {})
        user_id = metadata.get("user_id")
        credits = metadata.get("credits")
        
        if not user_id or not credits:
            logger.error(f"Invalid metadata: user_id={user_id}, credits={credits}")
            return JSONResponse({"status": "error", "message": "Invalid metadata"})
        
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
            
            logger.info(f"YooKassa payment processed: user_id={user_id}, credits={credits}, payment_id={payment_id}")
            
            # Уведомление
            from aiogram import Bot
            bot = Bot(token=settings.BOT_TOKEN)
            try:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=(
                        f"✅ <b>Оплата успешна!</b>\n\n"
                        f"💰 Начислено: {int(float(credits))} ген.\n"
                        f"⚡ Баланс: {int(user.balance)} ген."
                    ),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
            finally:
                await bot.session.close()
        
        return JSONResponse({"status": "ok"})
        
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")