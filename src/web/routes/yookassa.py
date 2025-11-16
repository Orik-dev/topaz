from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.services.payments import PaymentService
from aiogram import Bot
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yookassa", tags=["yookassa"])


@router.post("/webhook")
async def yookassa_webhook(request: Request):
    """YooKassa webhook"""
    try:
        data = await request.json()
        event_type = data.get("event")
        
        if event_type == "payment.succeeded":
            payment_object = data.get("object", {})
            payment_id = payment_object.get("id")
            
            if payment_id:
                async with async_session_maker() as session:
                    success = await PaymentService.process_yookassa_webhook(session, payment_id)
                    
                    if success:
                        # Уведомляем пользователя
                        metadata = payment_object.get("metadata", {})
                        telegram_id = metadata.get("telegram_id")
                        
                        if telegram_id:
                            bot = Bot(token=settings.BOT_TOKEN)
                            try:
                                await bot.send_message(
                                    chat_id=int(telegram_id),
                                    text="✅ Оплата успешна! Генерации зачислены на баланс."
                                )
                            finally:
                                await bot.session.close()
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}", exc_info=True)
        return {"status": "error"}