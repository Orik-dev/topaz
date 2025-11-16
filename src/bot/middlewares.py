from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.engine import async_session_maker
from src.db.models import User
from src.services.users import UserService
from sqlalchemy import select
from aiogram.fsm.context import FSMContext
import logging
import time

logger = logging.getLogger(__name__)


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для подключения к БД
    ✅ Создает async сессию для каждого запроса
    ✅ Автоматически закрывает сессию после обработки
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                # Коммитим только если не было ошибок
                await session.commit()
                return result
            except Exception as e:
                # Откатываем транзакцию при ошибке
                await session.rollback()
                logger.error(f"Error in handler, rolled back: {e}", exc_info=True)
                raise


class UserMiddleware(BaseMiddleware):
    """
    Middleware для получения/создания пользователя
    ✅ Автоматически создает пользователя при первом обращении
    ✅ Обновляет данные пользователя (username, имя)
    ✅ Добавляет пользователя в data["user"]
    """
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        session: AsyncSession = data.get("session")
        
        if not session:
            logger.warning("Session not found in middleware data")
            return await handler(event, data)
        
        # Получаем telegram_id в зависимости от типа события
        if isinstance(event, Message):
            telegram_user = event.from_user
        elif isinstance(event, CallbackQuery):
            telegram_user = event.from_user
        else:
            logger.warning(f"Unsupported event type: {type(event)}")
            return await handler(event, data)
        
        if not telegram_user:
            logger.warning("User not found in event")
            return await handler(event, data)
        
        try:
            # ✅ Получаем или создаем пользователя
            user = await UserService.get_or_create_user(
                session=session,
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name
            )
            
            # Flush чтобы пользователь был доступен в handler
            await session.flush()
            
            data["user"] = user
            
        except Exception as e:
            logger.error(f"Error in UserMiddleware: {e}", exc_info=True)
            # Продолжаем без пользователя, handler сам решит что делать
        
        return await handler(event, data)


class ClearStateOnCommandMiddleware(BaseMiddleware):
    """
    Middleware для очистки состояния при вводе команд
    ✅ Очищает FSM state при вводе определенных команд
    ✅ Предотвращает застревание в состояниях
    ✅ КАК В NANOBANANA!
    """
    
    # Команды, которые всегда очищают состояние
    CLEAR_COMMANDS = {
        "/start",
        "/help",
        "/buy",
        "/balance",
        "/bots",
        "/stats",
        "/broadcast"
    }
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем, является ли сообщение командой
        if event.text and event.text.startswith("/"):
            state: FSMContext = data.get("state")
            
            if state:
                current_state = await state.get_state()
                command = event.text.split()[0].lower()
                
                # ✅ Очищаем состояние для определенных команд
                if command in self.CLEAR_COMMANDS and current_state:
                    await state.clear()
                    logger.info(f"State cleared for command: {command}, user={event.from_user.id}")
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования всех запросов
    ✅ Логирует входящие сообщения и callback queries
    ✅ Измеряет время обработки
    ✅ Логирует ошибки
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        start_time = time.time()
        
        # Определяем тип события и логируем
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            chat_id = event.chat.id
            text = event.text or event.caption or "<no text>"
            
            logger.info(
                f"Message received: user_id={user_id}, chat_id={chat_id}, "
                f"text={text[:100]}"
            )
        
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            data_str = event.data or "<no data>"
            
            logger.info(
                f"Callback received: user_id={user_id}, data={data_str}"
            )
        
        try:
            # Обрабатываем событие
            result = await handler(event, data)
            
            # Логируем время обработки
            elapsed_time = time.time() - start_time
            logger.info(f"Request processed in {elapsed_time:.3f}s")
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"Error processing request (took {elapsed_time:.3f}s): {e}",
                exc_info=True
            )
            raise


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для защиты от флуда
    ✅ Ограничивает количество запросов в минуту
    ✅ Предотвращает спам
    """
    
    def __init__(self, rate_limit: int = 30):
        """
        rate_limit: максимум сообщений в минуту от одного пользователя
        """
        self.rate_limit = rate_limit
        self.user_requests: Dict[int, list] = {}
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        else:
            return await handler(event, data)
        
        if not user_id:
            return await handler(event, data)
        
        current_time = time.time()
        
        # Инициализируем список запросов для пользователя
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Удаляем запросы старше 1 минуты
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if current_time - req_time < 60
        ]
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            
            # Отправляем предупреждение только для Message
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Слишком много запросов. Подождите немного."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Слишком много запросов",
                    show_alert=True
                )
            
            return None
        
        # Добавляем текущий запрос
        self.user_requests[user_id].append(current_time)
        
        return await handler(event, data)


class AdminCheckMiddleware(BaseMiddleware):
    """
    Middleware для проверки админ прав
    ✅ Используется только для админ роутеров
    """
    
    def __init__(self, admin_ids: list[int]):
        self.admin_ids = admin_ids
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id if event.from_user else None
        
        if user_id not in self.admin_ids:
            logger.warning(f"Non-admin user {user_id} tried to access admin function")
            await event.answer("❌ У вас нет доступа к этой команде")
            return None
        
        return await handler(event, data)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware для глобальной обработки ошибок
    ✅ Ловит все необработанные исключения
    ✅ Отправляет красивое сообщение пользователю
    ✅ Логирует подробности ошибки
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            
            # Отправляем сообщение об ошибке пользователю
            if isinstance(event, Message):
                await event.answer(
                    "❌ Произошла ошибка. Попробуйте позже или напишите в поддержку.",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Произошла ошибка",
                    show_alert=True
                )
            
            # Не пробрасываем ошибку дальше
            return None