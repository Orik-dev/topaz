from arq.connections import RedisSettings
from src.core.config import settings


def get_redis_settings():
    """ARQ Redis settings"""
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB
    )