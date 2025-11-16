"""Broadcast service for mass messaging."""
import uuid
import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError

from src.db.models import BroadcastJob
from src.services.users import get_all_active_users
from src.core.logging import logger


async def create_broadcast(
    session: AsyncSession,
    created_by: int,
    text: str,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
) -> BroadcastJob:
    """Создать задачу рассылки."""
    users = await get_all_active_users(session)
    
    broadcast = BroadcastJob(
        id=str(uuid.uuid4()),
        created_by=created_by,
        text=text,
        status="queued",
        total=len(users),
        sent=0,
        failed=0,
        fallback=0,
        media_type=media_type,
        media_file_id=media_file_id,
        created_at=datetime.utcnow(),
    )
    
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    
    return broadcast


async def execute_broadcast(session: AsyncSession, bot: Bot, broadcast_id: str):
    """Выполнить рассылку."""
    result = await session.execute(select(BroadcastJob).where(BroadcastJob.id == broadcast_id))
    broadcast = result.scalar_one_or_none()
    
    if not broadcast or broadcast.status != "queued":
        return
    
    # Обновляем статус
    stmt = update(BroadcastJob).where(BroadcastJob.id == broadcast_id).values(status="running")
    await session.execute(stmt)
    await session.commit()
    
    users = await get_all_active_users(session)
    
    sent = 0
    failed = 0
    fallback = 0
    
    for user_id in users:
        try:
            if broadcast.media_type and broadcast.media_file_id:
                # Отправка с медиа
                if broadcast.media_type == "photo":
                    await bot.send_photo(user_id, broadcast.media_file_id, caption=broadcast.text)
                elif broadcast.media_type == "video":
                    await bot.send_video(user_id, broadcast.media_file_id, caption=broadcast.text)
                elif broadcast.media_type == "document":
                    await bot.send_document(user_id, broadcast.media_file_id, caption=broadcast.text)
            else:
                # Отправка текста
                await bot.send_message(user_id, broadcast.text)
            
            sent += 1
            
        except TelegramRetryAfter as e:
            logger.warning(f"Rate limit hit, waiting {e.retry_after} seconds")
            await asyncio.sleep(e.retry_after)
            fallback += 1
            
        except TelegramForbiddenError:
            logger.info(f"User {user_id} blocked the bot")
            failed += 1
            
        except Exception as e:
            logger.error(f"Failed to send to {user_id}: {e}")
            failed += 1
        
        # Маленькая задержка между сообщениями
        await asyncio.sleep(0.05)
    
    # Обновляем статистику
    stmt = (
        update(BroadcastJob)
        .where(BroadcastJob.id == broadcast_id)
        .values(
            status="completed",
            sent=sent,
            failed=failed,
            fallback=fallback,
        )
    )
    await session.execute(stmt)
    await session.commit()
    
    logger.info(f"Broadcast {broadcast_id} completed: {sent} sent, {failed} failed, {fallback} fallback")