from aiogram import Router
from . import commands, payment, stars, image, video, admin

def get_routers() -> Router:
    """Получить все роутеры"""
    router = Router()
    
    # Регистрируем в правильном порядке
    router.include_router(commands.router)
    router.include_router(payment.router)
    router.include_router(stars.router)
    router.include_router(image.router)
    router.include_router(video.router)
    router.include_router(admin.router)
    
    return router