"""Start and help handlers."""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.services.users import get_or_create_user, get_balance
from src.core.logging import logger

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    async with get_session() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username
        )
        balance = await get_balance(session, message.from_user.id)
    
    logger.info(f"User {message.from_user.id} started the bot")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
            InlineKeyboardButton(text="📊 Тарифы", callback_data="pricing"),
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"🎨 Я бот для улучшения фото и видео с помощью AI от Topaz Labs.\n\n"
        f"💳 Ваш баланс: <b>{balance}</b> кредитов\n\n"
        f"📸 Отправьте мне фото или видео, и я улучшу его качество!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(Command("help"))
@router.callback_query(F.data == "help")
async def cmd_help(event):
    """Handle /help command."""
    message = event.message if hasattr(event, 'message') else event
    
    help_text = (
        "🎨 <b>Как использовать бота:</b>\n\n"
        "1️⃣ Пополните баланс командой /balance\n"
        "2️⃣ Отправьте фото или видео\n"
        "3️⃣ Выберите модель обработки\n"
        "4️⃣ Дождитесь результата\n\n"
        
        "📸 <b>Модели для фото:</b>\n"
        "• Face Recovery - восстановление лиц\n"
        "• Photo Enhance - общее улучшение\n"
        "• Denoise - удаление шума\n"
        "• Sharpen - повышение резкости\n"
        "• Upscale - увеличение разрешения\n\n"
        
        "🎬 <b>Модели для видео:</b>\n"
        "• Enhance V3 - улучшение качества\n"
        "• Iris V1 - интерполяция кадров\n"
        "• Proteus V1 - максимальное качество\n\n"
        
        "💡 <b>Команды:</b>\n"
        "/start - главное меню\n"
        "/balance - баланс и пополнение\n"
        "/history - история обработки\n"
        "/help - эта справка\n\n"
        
        "❓ Есть вопросы? Напишите @support"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Тарифы", callback_data="pricing")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")],
    ])
    
    if hasattr(event, 'message'):
        await event.message.edit_text(help_text, reply_markup=keyboard, parse_mode="HTML")
        await event.answer()
    else:
        await message.answer(help_text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "pricing")
async def show_pricing(callback):
    """Show pricing information."""
    pricing_text = (
        "💰 <b>Стоимость обработки:</b>\n\n"
        
        "📸 <b>Изображения (за мегапиксель):</b>\n"
        "• Face Recovery: 2 кредита\n"
        "• Photo Enhance: 4 кредита\n"
        "• Denoise: 2 кредита\n"
        "• Sharpen: 2 кредита\n"
        "• Upscale: 4 кредита\n\n"
        
        "🎬 <b>Видео (за секунду):</b>\n"
        "• Enhance V3: 100 кредитов\n"
        "• Iris V1: 140 кредитов\n"
        "• Proteus V1: 200 кредитов\n\n"
        
        "📦 <b>Пакеты кредитов:</b>\n"
        "• 35 кредитов - 299₽\n"
        "• 85 кредитов - 690₽\n"
        "• 190 кредитов - 1490₽\n"
        "• 400 кредитов - 2990₽\n\n"
        
        "💡 Чем больше пакет, тем выгоднее!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="balance")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="help")],
    ])
    
    await callback.message.edit_text(pricing_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "start")
async def back_to_start(callback):
    """Return to start menu."""
    async with get_session() as session:
        balance = await get_balance(session, callback.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
            InlineKeyboardButton(text="📊 Тарифы", callback_data="pricing"),
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])
    
    await callback.message.edit_text(
        f"👋 Привет, {callback.from_user.first_name}!\n\n"
        f"🎨 Я бот для улучшения фото и видео с помощью AI от Topaz Labs.\n\n"
        f"💳 Ваш баланс: <b>{balance}</b> кредитов\n\n"
        f"📸 Отправьте мне фото или видео, и я улучшу его качество!",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()