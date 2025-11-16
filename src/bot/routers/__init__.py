from aiogram import Router
from . import commands, payment, stars, image, video, admin

def get_routers() -> Router:
    """Получить все роутеры в правильном порядке"""
    router = Router()
    
    # Правильный порядок: от специфичного к общему
    router.include_router(payment.router)  # Платежи YooKassa
    router.include_router(stars.router)     # Платежи Stars
    router.include_router(image.router)     # Обработка фото
    router.include_router(video.router)     # Обработка видео
    router.include_router(admin.router)     # Админ команды
    router.include_router(commands.router)  # Основные команды (последние)
    
    return router