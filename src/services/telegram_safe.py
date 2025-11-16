import logging
from typing import Optional, Union
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramAPIError,
)
import asyncio

log = logging.getLogger("telegram_safe")


async def safe_send_text(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
    disable_web_page_preview: bool = True,
) -> Optional[Message]:
    """
    Безопасная отправка текстового сообщения
    ✅ Защита от всех telegram ошибок
    """
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramRetryAfter as e:
        log.warning(f"Rate limit, retry after {e.retry_after}s: chat_id={chat_id}")
        await asyncio.sleep(e.retry_after)
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
        except Exception as retry_error:
            log.error(f"Retry failed: chat_id={chat_id}, error={retry_error}")
            return None
    except TelegramForbiddenError:
        log.warning(f"Bot blocked by user: chat_id={chat_id}")
        return None
    except TelegramBadRequest as e:
        log.error(f"Bad request: chat_id={chat_id}, error={e}")
        return None
    except TelegramServerError as e:
        log.error(f"Telegram server error: chat_id={chat_id}, error={e}")
        return None
    except TelegramAPIError as e:
        log.error(f"Telegram API error: chat_id={chat_id}, error={e}")
        return None
    except Exception as e:
        log.exception(f"Unexpected error sending message: chat_id={chat_id}, error={e}")
        return None


async def safe_send_photo(
    bot: Bot,
    chat_id: int,
    photo: Union[str, bytes],
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
) -> Optional[Message]:
    """
    Безопасная отправка фото
    """
    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramRetryAfter as e:
        log.warning(f"Rate limit, retry after {e.retry_after}s: chat_id={chat_id}")
        await asyncio.sleep(e.retry_after)
        try:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        except Exception:
            return None
    except TelegramForbiddenError:
        log.warning(f"Bot blocked by user: chat_id={chat_id}")
        return None
    except TelegramBadRequest as e:
        log.error(f"Bad request sending photo: chat_id={chat_id}, error={e}")
        return None
    except Exception as e:
        log.exception(f"Unexpected error sending photo: chat_id={chat_id}, error={e}")
        return None


async def safe_send_video(
    bot: Bot,
    chat_id: int,
    video: Union[str, bytes],
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
) -> Optional[Message]:
    """
    Безопасная отправка видео
    """
    try:
        return await bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramRetryAfter as e:
        log.warning(f"Rate limit, retry after {e.retry_after}s: chat_id={chat_id}")
        await asyncio.sleep(e.retry_after)
        try:
            return await bot.send_video(
                chat_id=chat_id,
                video=video,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        except Exception:
            return None
    except TelegramForbiddenError:
        log.warning(f"Bot blocked by user: chat_id={chat_id}")
        return None
    except TelegramBadRequest as e:
        log.error(f"Bad request sending video: chat_id={chat_id}, error={e}")
        return None
    except Exception as e:
        log.exception(f"Unexpected error sending video: chat_id={chat_id}, error={e}")
        return None


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "HTML",
) -> bool:
    """
    Безопасное редактирование сообщения
    """
    try:
        await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            log.debug(f"Message not modified: {e}")
            return True
        log.error(f"Bad request editing message: {e}")
        return False
    except TelegramForbiddenError:
        log.warning("Bot blocked by user")
        return False
    except Exception as e:
        log.exception(f"Unexpected error editing message: {e}")
        return False


async def safe_delete_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
) -> bool:
    """
    Безопасное удаление сообщения
    """
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as e:
        if "message to delete not found" in str(e).lower():
            log.debug(f"Message already deleted: message_id={message_id}")
            return True
        log.error(f"Bad request deleting message: {e}")
        return False
    except TelegramForbiddenError:
        log.warning(f"Cannot delete message: chat_id={chat_id}, message_id={message_id}")
        return False
    except Exception as e:
        log.exception(f"Unexpected error deleting message: {e}")
        return False


async def safe_answer(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> bool:
    """
    Безопасный ответ на callback query
    """
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        if "query is too old" in str(e).lower():
            log.debug("Callback query is too old")
            return True
        log.error(f"Bad request answering callback: {e}")
        return False
    except Exception as e:
        log.exception(f"Unexpected error answering callback: {e}")
        return False