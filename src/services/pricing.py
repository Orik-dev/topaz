# Topaz Image API pricing (x2)
IMAGE_ENHANCE_CREDITS = 10      # 5 credits * 2 = 10
IMAGE_UPSCALE_CREDITS = 20      # 10 credits * 2 = 20
IMAGE_DENOISE_CREDITS = 10      # 5 credits * 2 = 10

# Topaz Video API pricing (x2)
VIDEO_ENHANCE_CREDITS = 40      # 20 credits * 2 = 40
VIDEO_UPSCALE_CREDITS = 80      # 40 credits * 2 = 80
VIDEO_DENOISE_CREDITS = 40      # 20 credits * 2 = 40

# Пакеты для продажи (в рублях)
PACKS_RUB = [299, 599, 1490, 2990]

PACKS_CREDITS: dict[int, int] = {
    299: 50,
    599: 120,
    1490: 350,
    2990: 800,
}

def credits_for_rub(rub: int) -> int:
    return PACKS_CREDITS.get(rub, 0)

def get_task_credits(task_type: str, operation: str) -> int:
    """Возвращает стоимость операции"""
    if task_type == "image":
        return {
            "enhance": IMAGE_ENHANCE_CREDITS,
            "upscale": IMAGE_UPSCALE_CREDITS,
            "denoise": IMAGE_DENOISE_CREDITS,
        }.get(operation, IMAGE_ENHANCE_CREDITS)
    elif task_type == "video":
        return {
            "enhance": VIDEO_ENHANCE_CREDITS,
            "upscale": VIDEO_UPSCALE_CREDITS,
            "denoise": VIDEO_DENOISE_CREDITS,
        }.get(operation, VIDEO_ENHANCE_CREDITS)
    return 10