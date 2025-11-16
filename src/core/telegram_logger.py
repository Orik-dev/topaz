"""Telegram logger for sending critical errors to admins."""
import asyncio
from typing import Optional
from aiogram import Bot

from src.core.config import config
from src.core.logging import logger


class TelegramLogger:
    """Send log messages to Telegram admins."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the logger task."""
        self._task = asyncio.create_task(self._process_queue())
        logger.info("Telegram logger started")
    
    async def stop(self):
        """Stop the logger task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Telegram logger stopped")
    
    async def _process_queue(self):
        """Process messages from queue."""
        while True:
            try:
                message = await self.queue.get()
                await self._send_to_admins(message)
                await asyncio.sleep(1)  # Rate limiting
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telegram logger: {e}")
    
    async def _send_to_admins(self, message: str):
        """Send message to all admins."""
        for admin_id in config.ADMIN_IDS:
            try:
                await self.bot.send_message(admin_id, message, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send log to admin {admin_id}: {e}")
    
    def log_error(self, message: str, error: Optional[Exception] = None):
        """Log error to Telegram."""
        text = f"🔴 <b>ERROR</b>\n\n{message}"
        if error:
            text += f"\n\n<code>{type(error).__name__}: {str(error)}</code>"
        
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            logger.warning("Telegram logger queue is full")
    
    def log_warning(self, message: str):
        """Log warning to Telegram."""
        text = f"⚠️ <b>WARNING</b>\n\n{message}"
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            logger.warning("Telegram logger queue is full")
    
    def log_info(self, message: str):
        """Log info to Telegram."""
        text = f"ℹ️ <b>INFO</b>\n\n{message}"
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            logger.warning("Telegram logger queue is full")