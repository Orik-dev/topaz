from arq.connections import RedisSettings
from src.core.config import settings


def get_redis_settings() -> RedisSettings:
    """Получить настройки Redis для ARQ"""
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )