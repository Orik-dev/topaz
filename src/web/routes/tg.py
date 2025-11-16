from fastapi import APIRouter, Request, Header
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from src.core.config import settings
from src.bot.routers import get_routers
from src.bot.middlewares import DatabaseMiddleware, UserMiddleware, ClearStateOnCommandMiddleware
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tg", tags=["telegram"])

# Initialize bot and dispatcher
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# Register all routers
dp.include_router(get_routers())

# Register middlewares
dp.message.middleware(ClearStateOnCommandMiddleware())
dp.message.middleware(DatabaseMiddleware())
dp.message.middleware(UserMiddleware())
dp.callback_query.middleware(DatabaseMiddleware())
dp.callback_query.middleware(UserMiddleware())


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None)
):
    """Telegram webhook endpoint"""
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Invalid webhook secret token")
        return {"status": "error", "message": "Invalid secret token"}
    
    update_data = await request.json()
    update = Update(**update_data)
    
    await dp.feed_update(bot, update)
    
    return {"status": "ok"}