"""Job management service for image/video processing."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Job


async def create_job(
    session: AsyncSession,
    telegram_id: int,
    job_type: str,  # "image" or "video"
    model: str,
    credits_cost: int,
    input_file_id: str,
    input_file_size: int,
) -> Job:
    """Создать новую задачу обработки."""
    job = Job(
        id=str(uuid.uuid4()),
        telegram_id=telegram_id,
        type=job_type,
        model=model,
        status="pending",
        credits_cost=credits_cost,
        input_file_id=input_file_id,
        input_file_size=input_file_size,
        created_at=datetime.utcnow(),
    )
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    return job


async def get_job(session: AsyncSession, job_id: str) -> Optional[Job]:
    """Получить задачу по ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    status: str,
    topaz_job_id: Optional[str] = None,
    output_file_id: Optional[str] = None,
    error_message: Optional[str] = None,
) -> bool:
    """Обновить статус задачи."""
    values = {"status": status}
    
    if topaz_job_id:
        values["topaz_job_id"] = topaz_job_id
    
    if output_file_id:
        values["output_file_id"] = output_file_id
        values["completed_at"] = datetime.utcnow()
    
    if error_message:
        values["error_message"] = error_message
    
    stmt = update(Job).where(Job.id == job_id).values(**values)
    await session.execute(stmt)
    await session.commit()
    
    return True


async def get_user_jobs(session: AsyncSession, telegram_id: int, limit: int = 10) -> list[Job]:
    """Получить последние задачи пользователя."""
    result = await session.execute(
        select(Job)
        .where(Job.telegram_id == telegram_id)
        .order_by(Job.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())