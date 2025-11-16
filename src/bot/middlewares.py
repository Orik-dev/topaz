from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.services.users import UserService
import logging

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для подключения БД"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


class UserMiddleware(BaseMiddleware):
    """Middleware для получения/создания пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        session: AsyncSession = data.get("session")
        
        if isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user
        else:
            return await handler(event, data)
        
        user = await UserService.get_or_create_user(
            session=session,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
        
        data["user"] = user
        return await handler(event, data)


class ClearStateOnCommandMiddleware(BaseMiddleware):
    """Автоочистка стейтов при командах (ЗАЩИТА ОТ КОНФЛИКТОВ!)"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Очищаем стейт если это команда или кнопка главного меню
        if event.text:
            if event.text.startswith('/') or event.text in [
                "📸 Улучшить фото",
                "🎬 Улучшить видео", 
                "💰 Баланс",
                "💳 Пополнить",
                "ℹ️ Помощь"
            ]:
                state: FSMContext = data.get("state")
                if state:
                    await state.clear()
                    logger.info(f"State cleared for user {event.from_user.id}")
        
        return await handler(event, data)