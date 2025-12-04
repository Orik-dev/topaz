from fastapi import FastAPI
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
import redis.asyncio as redis
import logging

from src.core.config import settings
from src.core.logging import setup_logging
from src.bot.routers import get_routers
from src.bot.middlewares import (
    DatabaseMiddleware,
    UserMiddleware,
    ClearStateOnCommandMiddleware,
    LoggingMiddleware,
    ThrottlingMiddleware,
    ErrorHandlerMiddleware,
)
from src.web.routes import tg, yookassa, health

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    logger.info("Starting bot...")

    # --- Создаем bot ---
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # --- Создаем Redis storage для FSM ---
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=False,
    )
    storage = RedisStorage(
        redis=redis_client,
        key_builder=DefaultKeyBuilder(with_bot_id=True),
    )

    # --- Создаем dispatcher ---
    dp = Dispatcher(storage=storage)

    # ✅ Подключаем middlewares
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

    # --- Подключаем роутеры ---
    router = get_routers()
    dp.include_router(router)

    # --- Устанавливаем webhook (с защитой от флуда) ---
    webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"

    try:
        # 1) Смотрим текущее состояние вебхука
        info = await bot.get_webhook_info()
        current_url = info.url or ""

        if current_url == webhook_url:
            logger.info(f"Webhook уже установлен: {webhook_url}")
        else:
            try:
                await bot.set_webhook(
                    url=webhook_url,
                    secret_token=settings.WEBHOOK_SECRET,
                    drop_pending_updates=True,
                )
                logger.info(f"Webhook set: {webhook_url}")
            except TelegramRetryAfter as e:
                # Не роняем приложение, просто логируем и продолжаем
                logger.warning(
                    f"TelegramRetryAfter при set_webhook (retry_after={e.retry_after}). "
                    f"Пропускаем установку вебхука на старте."
                )
            except TelegramBadRequest as e:
                # Если, например, URL уже используется/некорректен
                logger.error(f"TelegramBadRequest при set_webhook: {e}")
            except Exception as e:
                logger.exception(f"Не удалось установить webhook: {e}")
    except Exception as e:
        # Ошибка при get_webhook_info — тоже не роняем воркер
        logger.exception(f"Не удалось получить webhook_info: {e}")

    # --- Кладём объекты в app.state для использования в роутерах ---
    app.state.bot = bot
    app.state.dp = dp
    app.state.redis = redis_client

    try:
        # Передаём управление приложению
        yield
    finally:
        # ✅ Корректный shutdown
        logger.info("Stopping bot...")
        try:
            # Не обязательно, но аккуратно пробуем убрать вебхук
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as e:
            logger.warning(f"Ошибка при delete_webhook: {e}")

        # Закрываем сессию бота (чтобы не было Unclosed client session)
        try:
            await bot.session.close()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии bot.session: {e}")

        # Закрываем Redis-клиент корректно (без aclose)
        try:
            await redis_client.close()
            await redis_client.connection_pool.disconnect()
        except Exception as e:
            logger.warning(f"Ошибка при закрытии Redis: {e}")

        logger.info("Bot stopped")


# Создаем FastAPI приложение
app = FastAPI(
    title="Topaz Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

# Подключаем routes
app.include_router(health.router, tags=["Health"])
app.include_router(tg.router, tags=["Telegram"])
app.include_router(yookassa.router, tags=["Payments"])
