from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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


def email_keyboard(package_id: str) -> InlineKeyboardMarkup:
    """Клавиатура ввода email (КАК В NANOBANANA!)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Чек не нужен", callback_data=f"no_receipt:{package_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


def image_models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора модели фото"""
    buttons = []
    
    # Группируем по категориям
    categories = {
        "enhance": "✨ Улучшение",
        "sharpen": "🔍 Резкость",
        "denoise": "🌟 Шумоподавление",
        "enhance_gen": "🎭 AI-улучшение",
        "sharpen_gen": "🎯 AI-резкость",
        "restore_gen": "🔄 Восстановление",
    }
    
    for category, title in categories.items():
        models = {k: v for k, v in IMAGE_MODELS.items() if v["category"] == category}
        if models:
            buttons.append([InlineKeyboardButton(text=f"━━━ {title} ━━━", callback_data="ignore")])
            for model_name, model_info in models.items():
                cost_emoji = "💎" if model_info["cost"] > 1 else "💰"
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{model_info['description']} {cost_emoji}{model_info['cost']}",
                        callback_data=f"img_model:{model_name}"
                    )
                ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def video_models_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора модели видео"""
    buttons = []
    
    for model_key, model_info in VIDEO_MODELS.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{model_info['description']} 💰{model_info['cost_per_minute']}/мин",
                callback_data=f"vid_model:{model_key}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Кнопка отмены"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])