"""User management service."""
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str] = None) -> User:
    """Получить или создать пользователя."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            balance=0,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    return user


async def update_balance(session: AsyncSession, telegram_id: int, amount: int) -> bool:
    """Изменить баланс пользователя (положительный или отрицательный amount)."""
    stmt = (
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(balance=User.balance + amount)
        .returning(User.balance)
    )
    result = await session.execute(stmt)
    await session.commit()
    
    new_balance = result.scalar_one_or_none()
    return new_balance is not None and new_balance >= 0


async def get_balance(session: AsyncSession, telegram_id: int) -> int:
    """Получить баланс пользователя."""
    result = await session.execute(
        select(User.balance).where(User.telegram_id == telegram_id)
    )
    balance = result.scalar_one_or_none()
    return balance if balance is not None else 0


async def get_all_active_users(session: AsyncSession) -> list[int]:
    """Получить список всех активных пользователей для рассылки."""
    result = await session.execute(
        select(User.telegram_id).where(User.is_active == True)
    )
    return [row[0] for row in result.all()]


async def ban_user(session: AsyncSession, telegram_id: int) -> bool:
    """Забанить пользователя."""
    stmt = update(User).where(User.telegram_id == telegram_id).values(is_active=False)
    await session.execute(stmt)
    await session.commit()
    return True


async def unban_user(session: AsyncSession, telegram_id: int) -> bool:
    """Разбанить пользователя."""
    stmt = update(User).where(User.telegram_id == telegram_id).values(is_active=True)
    await session.execute(stmt)
    await session.commit()
    return True