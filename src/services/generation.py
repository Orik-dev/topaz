from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Task, TaskStatus, TaskType, User
from arq import create_pool
from src.workers.settings import get_redis_settings
from typing import Optional
import logging
import json

logger = logging.getLogger(__name__)


class GenerationService:
    @staticmethod
    async def create_task(
        session: AsyncSession,
        user: User,
        task_type: TaskType,
        model: str,
        cost: float,
        input_file_id: Optional[str] = None,
        parameters: Optional[dict] = None
    ) -> Task:
        """Создать задачу"""
        task = Task(
            user_id=user.id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            cost=cost,
            model=model,
            input_file_id=input_file_id,
            parameters=json.dumps(parameters) if parameters else None
        )
        session.add(task)
        await session.flush()
        return task

    @staticmethod
    async def enqueue_image_task(task_id: int, user_telegram_id: int, image_data: bytes):
        """Поставить в очередь обработку фото"""
        redis = await create_pool(get_redis_settings())
        try:
            await redis.enqueue_job(
                'process_image_task',
                task_id,
                user_telegram_id,
                image_data
            )
            logger.info(f"Image task {task_id} enqueued")
        finally:
            await redis.close()

    @staticmethod
    async def enqueue_video_task(task_id: int, user_telegram_id: int, video_file_id: str):
        """Поставить в очередь обработку видео"""
        redis = await create_pool(get_redis_settings())
        try:
            await redis.enqueue_job(
                'process_video_task',
                task_id,
                user_telegram_id,
                video_file_id
            )
            logger.info(f"Video task {task_id} enqueued")
        finally:
            await redis.close()