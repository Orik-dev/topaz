from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from src.core.config import settings
from src.core.logging import logger
from src.bot.routers import commands, stars
from src.bot.middlewares import DatabaseMiddleware, UserMiddleware, ClearStateOnCommandMiddleware
from src.web.routes import tg, yookassa, health
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    # Startup
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Set webhook
    webhook_url = f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.WEBHOOK_SECRET,
        drop_pending_updates=True
    )
    
    logger.info(f"Webhook set: {webhook_url}")
    
    yield
    
    # Shutdown
    await bot.delete_webhook()
    await bot.session.close()
    logger.info("Bot stopped")


app = FastAPI(title="Topaz Bot API", lifespan=lifespan)

# Routes
app.include_router(tg.router)
app.include_router(yookassa.router)
app.include_router(health.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Topaz Bot"}