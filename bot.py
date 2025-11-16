"""Main bot file."""
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from src.core.config import config
from src.core.logging import logger
from src.core.telegram_logger import TelegramLogger
from src.db.engine import init_db, close_db
from src.handlers import setup_routers
from src.handlers.webhook import setup_webhook_routes
from src.utils.cleanup import start_cleanup_worker


async def on_startup(bot: Bot, dp: Dispatcher):
    """On bot startup."""
    logger.info("Starting bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start cleanup worker
    start_cleanup_worker()
    logger.info("Cleanup worker started")
    
    # Create temp directory
    Path(config.TEMP_DIR).mkdir(parents=True, exist_ok=True)
    
    # Start telegram logger
    if hasattr(dp, "telegram_logger"):
        await dp.telegram_logger.start()
    
    # Notify admins
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "✅ <b>Бот запущен!</b>\n\n"
                f"Режим: {'Webhook' if config.TOPAZ_WEBHOOK_URL else 'Polling'}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    logger.info("Bot started successfully")


async def on_shutdown(bot: Bot, dp: Dispatcher):
    """On bot shutdown."""
    logger.info("Shutting down bot...")
    
    # Stop telegram logger
    if hasattr(dp, "telegram_logger"):
        await dp.telegram_logger.stop()
    
    # Close database
    await close_db()
    logger.info("Database closed")
    
    # Notify admins
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "⛔️ <b>Бот остановлен</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    logger.info("Bot stopped")


async def main():
    """Main function."""
    # Initialize bot
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize dispatcher with memory storage
    dp = Dispatcher(storage=MemoryStorage())
    
    # Setup telegram logger
    telegram_logger = TelegramLogger(bot)
    dp.telegram_logger = telegram_logger
    
    # Setup routers
    main_router = setup_routers()
    dp.include_router(main_router)
    
    # Register startup/shutdown handlers
    dp.startup.register(lambda: on_startup(bot, dp))
    dp.shutdown.register(lambda: on_shutdown(bot, dp))
    
    try:
        if config.TOPAZ_WEBHOOK_URL:
            # Webhook mode (for production)
            logger.info("Starting in webhook mode")
            
            # Create web app
            app = web.Application()
            app["bot"] = bot
            
            # Setup webhook routes
            setup_webhook_routes(app)
            
            # Setup aiogram webhook
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
            
            webhook_path = "/webhook/telegram"
            webhook_url = f"{config.TOPAZ_WEBHOOK_URL}{webhook_path}"
            
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
                allowed_updates=dp.resolve_used_update_types()
            )
            
            SimpleRequestHandler(
                dispatcher=dp,
                bot=bot,
            ).register(app, path=webhook_path)
            
            setup_application(app, dp, bot=bot)
            
            # Run web app
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8080)
            
            await on_startup(bot, dp)
            await site.start()
            
            logger.info(f"Webhook set to {webhook_url}")
            logger.info("Web server started on http://0.0.0.0:8080")
            
            # Keep running
            await asyncio.Event().wait()
            
        else:
            # Polling mode (for development)
            logger.info("Starting in polling mode")
            
            # Delete webhook if exists
            await bot.delete_webhook(drop_pending_updates=True)
            
            # Start polling
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                on_startup=lambda: on_startup(bot, dp),
                on_shutdown=lambda: on_shutdown(bot, dp)
            )
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")