"""Database engine configuration."""
from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from core.config import settings

engine = create_async_engine(
    settings.DB_DSN,
    pool_pre_ping=True,
    pool_recycle=180,
    pool_size=30,
    pool_timeout=10,
    pool_use_lifo=True,
    max_overflow=70,
    connect_args={"connect_timeout": 5},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)