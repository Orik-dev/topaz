"""Rate limiter for Topaz API to prevent quota exhaustion."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict
from collections import deque

from src.core.logging import logger


class TopazRateLimiter:
    """
    Rate limiter для Topaz API.
    
    Ограничения:
    - 100 запросов в минуту
    - 1000 запросов в час
    """
    
    def __init__(self):
        self._minute_window: deque = deque(maxlen=100)
        self._hour_window: deque = deque(maxlen=1000)
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Получить разрешение на запрос."""
        async with self._lock:
            now = datetime.utcnow()
            
            # Clean old requests
            self._clean_window(self._minute_window, now, timedelta(minutes=1))
            self._clean_window(self._hour_window, now, timedelta(hours=1))
            
            # Check limits
            if len(self._minute_window) >= 100:
                wait_time = (self._minute_window[0] + timedelta(minutes=1) - now).total_seconds()
                logger.warning(f"Rate limit: minute window full, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                return await self.acquire()
            
            if len(self._hour_window) >= 1000:
                wait_time = (self._hour_window[0] + timedelta(hours=1) - now).total_seconds()
                logger.warning(f"Rate limit: hour window full, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                return await self.acquire()
            
            # Record request
            self._minute_window.append(now)
            self._hour_window.append(now)
    
    def _clean_window(self, window: deque, now: datetime, duration: timedelta):
        """Remove expired requests from window."""
        cutoff = now - duration
        while window and window[0] < cutoff:
            window.popleft()
    
    def get_stats(self) -> Dict[str, int]:
        """Get current rate limit stats."""
        return {
            "minute_requests": len(self._minute_window),
            "hour_requests": len(self._hour_window),
            "minute_remaining": 100 - len(self._minute_window),
            "hour_remaining": 1000 - len(self._hour_window),
        }


# Global rate limiter instance
rate_limiter = TopazRateLimiter()