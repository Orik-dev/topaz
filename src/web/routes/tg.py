from fastapi import APIRouter, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from src.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/tg/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint
    ✅ С проверкой секретного токена
    """
    # Проверяем секретный токен
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_token != settings.WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook secret token")
        raise HTTPException(status_code=403, detail="Forbidden")
    
    try:
        update_dict = await request.json()
        
        # Получаем bot и dispatcher из app state
        bot: Bot = request.app.state.bot
        dp: Dispatcher = request.app.state.dp
        
        # Обрабатываем update
        update = Update(**update_dict)
        await dp.feed_update(bot, update)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")