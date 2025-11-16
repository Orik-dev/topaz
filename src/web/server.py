from fastapi import FastAPI
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import redis.asyncio as redis
from src.core.config import settings
from src.core.logging import setup_logging
from src.bot.routers import get_routers
from src.bot.middlewares import (
    DatabaseMiddleware,
    UserMiddleware,
    ClearStateOnCommandMiddleware,
    LoggingMiddleware,
    ThrottlingMiddleware,
    ErrorHandlerMiddleware
)
from src.web.routes import tg, yookassa, health
import logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    logger.info("Starting bot...")
    
    # Создаем bot
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем Redis storage для FSM
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=False
    )
    storage = RedisStorage(
        redis=redis_client,
        key_builder=DefaultKeyBuilder(with_bot_id=True)
    )
    
    # Создаем dispatcher
    dp = Dispatcher(storage=storage)
    
    # ✅ ПОДКЛЮЧАЕМ MIDDLEWARES
    dp.message.outer_middleware(ErrorHandlerMiddleware())
    dp.callback_query.outer_middleware(ErrorHandlerMiddleware())
    
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    dp.message.middleware(ThrottlingMiddleware(rate_limit=30))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=60))
    
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())
    
    dp.message.middleware(ClearStateOnCommandMiddleware())
    
    # Подключаем роутеры
    router = get_routers()
    dp.include_router(router)
    
    # Устанавливаем webhook
    webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    
    logger.info(f"Webhook set: {webhook_url}")
    
    # Сохраняем в app state
    app.state.bot = bot
    app.state.dp = dp
    
    yield
    
    # ✅ Shutdown - ПРАВИЛЬНОЕ ЗАКРЫТИЕ
    logger.info("Stopping bot...")
    await bot.delete_webhook()
    await bot.session.close()  # Закрываем сессию бота
    await redis_client.aclose()  # Закрываем Redis
    logger.info("Bot stopped")


# Создаем FastAPI приложение
app = FastAPI(
    title="Topaz Bot API",
    version="1.0.0",
    lifespan=lifespan
)

# Подключаем routes
app.include_router(health.router, tags=["Health"])
app.include_router(tg.router, tags=["Telegram"])
app.include_router(yookassa.router, tags=["Payments"])