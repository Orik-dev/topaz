"""Pricing configuration for Topaz Labs API.

Цены в 2 раза выше прайса API в рублях.
Курс: 1 USD = 100 RUB (примерно)
"""

# Стоимость 1 кредита в рублях
CREDIT_PRICE_RUB = 10

# Модели для изображений (цена за мегапиксель в USD * 2 * 100)
IMAGE_MODELS_CREDITS = {
    "face-recovery-v1": 20,      # $0.001 * 2 * 100 = 20 руб за МП
    "photo-enhance-v1": 40,      # $0.002 * 2 * 100 = 40 руб за МП
    "denoise-v1": 20,            # $0.001 * 2 * 100 = 20 руб за МП
    "sharpen-v1": 20,            # $0.001 * 2 * 100 = 20 руб за МП
    "upscale-v1": 40,            # $0.002 * 2 * 100 = 40 руб за МП
}

# Модели для видео (цена за секунду в USD * 2 * 100)
VIDEO_MODELS_CREDITS = {
    "enhance-v3": 1000,   # $0.05 * 2 * 100 = 1000 руб за сек
    "iris-v1": 1400,      # $0.07 * 2 * 100 = 1400 руб за сек
    "proteus-v1": 2000,   # $0.10 * 2 * 100 = 2000 руб за сек
}

# Пакеты пополнения (рубли → кредиты)
PACKS_RUB = [299, 690, 1490, 2990]

PACKS_CREDITS: dict[int, int] = {
    299: 35,      # ~8.5 руб/кредит
    690: 85,      # ~8.1 руб/кредит
    1490: 190,    # ~7.8 руб/кредит
    2990: 400,    # ~7.5 руб/кредит
}


def credits_for_rub(rub: int) -> int:
    """Конвертация рублей в кредиты."""
    return PACKS_CREDITS.get(rub, 0)


def calculate_image_cost(model: str, megapixels: float) -> int:
    """Расчёт стоимости обработки изображения в кредитах."""
    cost_per_mp = IMAGE_MODELS_CREDITS.get(model, 40)
    # Минимум 1 кредит
    return max(1, int(cost_per_mp * megapixels / CREDIT_PRICE_RUB))


def calculate_video_cost(model: str, duration_seconds: float) -> int:
    """Расчёт стоимости обработки видео в кредитах."""
    cost_per_sec = VIDEO_MODELS_CREDITS.get(model, 1000)
    # Минимум 1 кредит
    return max(1, int(cost_per_sec * duration_seconds / CREDIT_PRICE_RUB))