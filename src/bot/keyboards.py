from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.pricing import GENERATION_PACKAGES


def main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Улучшить фото"), KeyboardButton(text="🎬 Улучшить видео")],
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="💳 Пополнить")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True
    )


def topup_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура пополнения"""
    buttons = []
    
    for package_id, info in GENERATION_PACKAGES.items():
        gens = info["generations"]
        bonus = info["bonus"]
        price = info["price"]
        
        text = f"{gens} ген."
        if bonus > 0:
            text += f" +{bonus} 🎁"
        text += f" - {price}₽"
        
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"buy:{package_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="⭐ Оплата Stars", callback_data="buy_stars")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_method_keyboard(package_id: str) -> InlineKeyboardMarkup:
    """Выбор метода оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Карта/СБП (YooKassa)", callback_data=f"pay_yoo:{package_id}")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars:{package_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="topup")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])