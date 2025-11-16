from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from src.services.pricing import GENERATION_PACKAGES, IMAGE_MODELS, VIDEO_MODELS


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
    """Клавиатура пополнения (КАК В NANOBANANA!)"""
    buttons = []
    
    for package_id, info in GENERATION_PACKAGES.items():
        gens = info["generations"]
        bonus = info["bonus"]
        price = info["price"]
        
        text = f"{gens} ген."
        if bonus > 0:
            text += f" +{bonus} 🎁"
        text += f" — {price}₽"
        
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"buy:{package_id}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_method_keyboard(package_id: str) -> InlineKeyboardMarkup:
    """Выбор метода оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Карта/СБП (YooKassa)", callback_data=f"pay_yoo:{package_id}")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay_stars:{package_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy")],
    ])


def email_keyboard(package_id: str) -> InlineKeyboardMarkup:
    """Клавиатура ввода email (КАК В NANOBANANA!)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Чек не нужен", callback_data=f"no_receipt:{package_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy:{package_id}")],
    ])


def image_models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора модели для фото"""
    buttons = []
    
    for model_key, model_info in IMAGE_MODELS.items():
        text = f"{model_info['description']} — {int(model_info['cost'])} ген."
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"img_model:{model_key}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def video_models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора модели для видео"""
    buttons = []
    
    for model_key, model_info in VIDEO_MODELS.items():
        cost_per_min = model_info['cost_per_minute']
        text = f"{model_info['description']} — {int(cost_per_min)} ген./мин"
        buttons.append([
            InlineKeyboardButton(
                text=text,
                callback_data=f"vid_model:{model_key}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])