import logging
from typing import Tuple
import redis.asyncio as aioredis
from src.core.config import settings

logger = logging.getLogger(__name__)


class UserRateLimiter:
    """Rate limiter для пользователей"""
    
    async def check_limit(
        self,
        user_id: int,
        action: str,
        limit: int,
        window: int
    ) -> Tuple[bool, int]:
        """
        Проверка лимита
        
        Returns:
            (allowed: bool, remaining_seconds: int)
        """
        redis = None
        try:
            redis = await aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB_CACHE
            )
            
            key = f"rate_limit:{user_id}:{action}"
            
            # Получаем текущее количество
            count = await redis.incr(key)
            
            if count == 1:
                # Первый запрос - устанавливаем TTL
                await redis.expire(key, window)
            
            if count > limit:
                # Получаем оставшееся время
                ttl = await redis.ttl(key)
                return False, ttl if ttl > 0 else window
            
            return True, 0
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            # При ошибке разрешаем запрос
            return True, 0
        finally:
            if redis:
                try:
                    await redis.close()
                except Exception:
                    pass


rate_limiter = UserRateLimiter()