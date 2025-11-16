from fastapi import APIRouter
from sqlalchemy import text
from src.db.engine import async_session_maker
import redis.asyncio as redis
from src.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        
        # Check Redis
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        
        return {"status": "healthy", "database": "ok", "redis": "ok"}
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}