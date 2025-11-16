from typing import Dict, Any

# Базовые цены Topaz API в USD (из документации)
# Цены приблизительные, основаны на credits consumption
TOPAZ_BASE_PRICES_USD = {
    # Standard модели (дешевле)
    "Standard V2": 0.02,
    "Low Resolution V2": 0.02,
    "High Fidelity V2": 0.02,
    "CGI": 0.02,
    "Text Refine": 0.02,
    
    # Sharpen модели
    "Standard": 0.015,
    "Strong": 0.02,
    "Lens Blur": 0.015,
    "Lens Blur V2": 0.02,
    "Motion Blur": 0.015,
    "Natural": 0.015,
    "Refocus": 0.015,
    
    # Denoise модели
    "Normal": 0.015,
    "Strong": 0.02,
    "Extreme": 0.02,
    
    # Generative модели (дороже!)
    "Standard MAX": 0.05,
    "Redefine": 0.05,
    "Recovery": 0.04,
    "Recovery V2": 0.04,
    "Super Focus": 0.04,
    "Super Focus V2": 0.05,
    "Dust-Scratch": 0.05,
    
    # Lighting модели
    "Adjust": 0.01,
    "White Balance": 0.01,
}

# Video модели (цена за минуту)
TOPAZ_VIDEO_PRICES_USD = {
    "prob-4": 0.10,      # Proteus
    "ahq-12": 0.12,      # Artemis HQ
    "amq-13": 0.10,      # Artemis MQ
    "nyx-3": 0.08,       # Nyx
    "nxf-1": 0.06,       # Nyx Fast
    "apo-8": 0.15,       # Apollo (interpolation)
    "apf-2": 0.12,       # Apollo Fast
    "chr-2": 0.12,       # Chronos
    "rhea-1": 0.20,      # Rhea (4x upscale)
    "ghq-5": 0.15,       # Gaia HQ
}

# Курс USD → RUB
USD_TO_RUB = 95.0
MARKUP = 2.0  # x2 наценка


def calculate_generations(usd_price: float) -> int:
    """Конвертация USD → Генерации (с наценкой x2)"""
    price_rub = usd_price * USD_TO_RUB * MARKUP  # x2!
    # 1 генерация ≈ 4 рубля
    generations = max(1, round(price_rub / 4))
    return generations


# Все модели фото с ПОНЯТНЫМИ названиями и ценами в ГЕНЕРАЦИЯХ
IMAGE_MODELS = {
    # Enhance модели
    "Standard V2": {
        "name": "Standard V2",
        "description": "✨ Улучшение фото",
        "category": "enhance",
        "endpoint": "enhance",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Standard V2"])  # 1 ген
    },
    "Low Resolution V2": {
        "name": "Low Resolution V2",
        "description": "📱 Низкое качество → HD",
        "category": "enhance",
        "endpoint": "enhance",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Low Resolution V2"])  # 1 ген
    },
    "High Fidelity V2": {
        "name": "High Fidelity V2",
        "description": "🎨 Максимальная детализация",
        "category": "enhance",
        "endpoint": "enhance",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["High Fidelity V2"])  # 1 ген
    },
    "CGI": {
        "name": "CGI",
        "description": "🎮 Для 3D графики",
        "category": "enhance",
        "endpoint": "enhance",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["CGI"])  # 1 ген
    },
    "Text Refine": {
        "name": "Text Refine",
        "description": "📝 Улучшение текста на фото",
        "category": "enhance",
        "endpoint": "enhance",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Text Refine"])  # 1 ген
    },
    
    # Sharpen модели
    "Standard": {
        "name": "Standard",
        "description": "🔍 Убрать размытие",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Standard"])  # 1 ген
    },
    "Strong": {
        "name": "Strong",
        "description": "💪 Сильная резкость",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Strong"])  # 1 ген
    },
    "Lens Blur": {
        "name": "Lens Blur",
        "description": "📷 Исправить фокус",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Lens Blur"])  # 1 ген
    },
    "Lens Blur V2": {
        "name": "Lens Blur V2",
        "description": "📷 Фокус V2",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Lens Blur V2"])  # 1 ген
    },
    "Motion Blur": {
        "name": "Motion Blur",
        "description": "🏃 Убрать смазывание",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Motion Blur"])  # 1 ген
    },
    "Natural": {
        "name": "Natural",
        "description": "🌿 Естественная резкость",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Natural"])  # 1 ген
    },
    "Refocus": {
        "name": "Refocus",
        "description": "🎯 Перефокусировка",
        "category": "sharpen",
        "endpoint": "sharpen",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Refocus"])  # 1 ген
    },
    
    # Denoise модели
    "Normal": {
        "name": "Normal",
        "description": "🌟 Убрать шум",
        "category": "denoise",
        "endpoint": "denoise",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Normal"])  # 1 ген
    },
    "Strong Denoise": {
        "name": "Strong",
        "description": "✨ Сильное шумоподавление",
        "category": "denoise",
        "endpoint": "denoise",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Strong"])  # 1 ген
    },
    "Extreme": {
        "name": "Extreme",
        "description": "🚀 Экстремальный денойз",
        "category": "denoise",
        "endpoint": "denoise",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Extreme"])  # 1 ген
    },
    
    # Generative модели (ДОРОЖЕ!)
    "Redefine": {
        "name": "Redefine",
        "description": "🎭 AI-улучшение (креативное)",
        "category": "enhance_gen",
        "endpoint": "enhance-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Redefine"])  # 2 ген
    },
    "Recovery": {
        "name": "Recovery",
        "description": "🔄 Восстановление старых фото",
        "category": "enhance_gen",
        "endpoint": "enhance-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Recovery"])  # 2 ген
    },
    "Recovery V2": {
        "name": "Recovery V2",
        "description": "🔄 Восстановление V2",
        "category": "enhance_gen",
        "endpoint": "enhance-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Recovery V2"])  # 2 ген
    },
    "Super Focus": {
        "name": "Super Focus",
        "description": "🎯 Супер фокус AI",
        "category": "sharpen_gen",
        "endpoint": "sharpen-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Super Focus"])  # 2 ген
    },
    "Super Focus V2": {
        "name": "Super Focus V2",
        "description": "🎯 Супер фокус V2",
        "category": "sharpen_gen",
        "endpoint": "sharpen-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Super Focus V2"])  # 2 ген
    },
    "Dust-Scratch": {
        "name": "Dust-Scratch",
        "description": "🧹 Убрать царапины/пыль",
        "category": "restore_gen",
        "endpoint": "restore-gen/async",
        "cost": calculate_generations(TOPAZ_BASE_PRICES_USD["Dust-Scratch"])  # 2 ген
    },
}

# Модели видео
VIDEO_MODELS = {
    "Proteus prob-4": {
        "name": "prob-4",
        "model": "prob-4",
        "description": "✨ Улучшение (универсал)",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["prob-4"])  # 5 ген/мин
    },
    "Artemis ahq-12": {
        "name": "ahq-12",
        "model": "ahq-12",
        "description": "🎬 Денойз + резкость HQ",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["ahq-12"])  # 6 ген/мин
    },
    "Artemis amq-13": {
        "name": "amq-13",
        "model": "amq-13",
        "description": "🎬 Денойз + резкость MQ",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["amq-13"])  # 5 ген/мин
    },
    "Nyx nyx-3": {
        "name": "nyx-3",
        "model": "nyx-3",
        "description": "🌟 Шумоподавление",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["nyx-3"])  # 4 ген/мин
    },
    "Nyx nxf-1": {
        "name": "nxf-1",
        "model": "nxf-1",
        "description": "⚡ Денойз быстрый",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["nxf-1"])  # 3 ген/мин
    },
    "Apollo apo-8": {
        "name": "apo-8",
        "model": "apo-8",
        "description": "⏱️ 60 FPS (slowmo 8x)",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["apo-8"])  # 7 ген/мин
    },
    "Apollo apf-2": {
        "name": "apf-2",
        "model": "apf-2",
        "description": "⏱️ Интерполяция быстрая",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["apf-2"])  # 6 ген/мин
    },
    "Chronos chr-2": {
        "name": "chr-2",
        "model": "chr-2",
        "description": "🕐 Конвертация FPS",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["chr-2"])  # 6 ген/мин
    },
    "Rhea rhea-1": {
        "name": "rhea-1",
        "model": "rhea-1",
        "description": "🚀 AI-апскейл 4x",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["rhea-1"])  # 10 ген/мин
    },
    "Gaia ghq-5": {
        "name": "ghq-5",
        "model": "ghq-5",
        "description": "🎮 Для GenAI/CGI",
        "cost_per_minute": calculate_generations(TOPAZ_VIDEO_PRICES_USD["ghq-5"])  # 7 ген/мин
    },
}

# Пакеты генераций
GENERATION_PACKAGES = {
    "50": {"generations": 50, "price": 100, "bonus": 0},
    "250": {"generations": 250, "price": 450, "bonus": 50},
    "500": {"generations": 500, "price": 850, "bonus": 100},
    "2500": {"generations": 2500, "price": 4000, "bonus": 500},
}


def get_image_models_by_category(category: str = None) -> Dict[str, Any]:
    """Получить модели фото по категории"""
    if category:
        return {k: v for k, v in IMAGE_MODELS.items() if v["category"] == category}
    return IMAGE_MODELS


def get_video_models() -> Dict[str, Any]:
    """Получить модели видео"""
    return VIDEO_MODELS


def get_task_cost(task_type: str, model: str = None, duration_minutes: float = 1.0) -> int:
    """Стоимость задачи в генерациях"""
    if task_type == "video_enhance":
        if model and model in VIDEO_MODELS:
            return int(VIDEO_MODELS[model]["cost_per_minute"] * max(1.0, duration_minutes))
        return int(5 * max(1.0, duration_minutes))
    
    # Image
    if model and model in IMAGE_MODELS:
        return IMAGE_MODELS[model]["cost"]
    return 1


def get_package_info(package_id: str) -> Dict[str, Any]:
    """Информация о пакете"""
    return GENERATION_PACKAGES.get(package_id, GENERATION_PACKAGES["50"])


def calculate_stars_amount(price_rub: float) -> int:
    """Конвертация рублей в Stars"""
    from src.core.config import settings
    return max(1, int(price_rub / settings.STARS_CONVERSION_RATE))