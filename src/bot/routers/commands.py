from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from src.db.models import User
from src.bot.keyboards import main_keyboard
from src.core.config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Команда /start"""
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"🤖 Я бот для улучшения фото и видео с помощью Topaz AI\n\n"
        f"⚡ Ваш баланс: {int(user.balance)} ген.\n\n"
        f"📸 Отправьте фото или видео для начала работы\n"
        f"💳 Пополнить баланс: /buy\n\n"
        f"Выберите действие:",
        reply_markup=main_keyboard()
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """Команда /help"""
    await message.answer(
        f"📖 <b>Справка</b>\n\n"
        f"<b>Как использовать:</b>\n"
        f"📸 Улучшить фото - выберите модель (от 1 ген.)\n"
        f"🎬 Улучшить видео - выберите модель (от 3 ген./мин)\n\n"
        f"<b>Пополнение:</b>\n"
        f"💳 Карта/СБП через YooKassa\n"
        f"⭐ Telegram Stars\n\n"
        f"<b>Возврат генераций:</b>\n"
        f"При ошибке обработки генерации возвращаются автоматически\n\n"
        f"💬 Поддержка: @{settings.SUPPORT_USERNAME}",
        parse_mode="HTML"
    )


@router.message(Command("bots"))
async def cmd_bots(message: Message):
    """Команда /bots (КАК В NANOBANANA!)"""
    bots_text = (
        "🤖 <b>Наши боты:</b>\n\n"
        "🎨 <a href='https://t.me/YourTopazBot'>Topaz AI Bot</a> - Улучшение фото/видео\n"
        "🍌 <a href='https://t.me/YourNanoBananaBot'>NanoBanana Bot</a> - Генерация изображений\n"
        "🎥 <a href='https://t.me/YourSoraBot'>Sora AI Bot</a> - Создание видео\n"
        "🤖 <a href='https://t.me/YourDeepSeekBot'>DeepSeek Bot</a> - ИИ ассистент\n\n"
        f"💬 Поддержка: @{settings.SUPPORT_USERNAME}"
    )
    
    await message.answer(bots_text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(F.text == "💰 Баланс")
@router.message(Command("balance"))
async def cmd_balance(message: Message, user: User):
    """Показать баланс"""
    await message.answer(
        f"💰 <b>Ваш баланс</b>\n\n"
        f"⚡ Генераций: {int(user.balance)}\n\n"
        f"📸 Фото: от 1 ген.\n"
        f"🎬 Видео: от 3 ген./мин\n\n"
        f"💳 Пополнить: /buy",
        parse_mode="HTML"
    )
    