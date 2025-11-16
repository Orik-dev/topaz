from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, Task, TaskType, TaskStatus
from arq import create_pool
from src.workers.settings import get_redis_settings
import logging

logger = logging.getLogger(__name__)


class GenerationService:
    """Сервис для работы с генерациями"""
    
    @staticmethod
    async def create_task(
        session: AsyncSession,
        user: User,
        task_type: TaskType,
        model: str,
        cost: float,
        input_file_id: str = None,
        parameters: dict = None
    ) -> Task:
        """Создать задачу"""
        import json
        
        task = Task(
            user_id=user.id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            model=model,
            cost=cost,
            input_file_id=input_file_id,
            parameters=json.dumps(parameters) if parameters else None
        )
        
        session.add(task)
        await session.flush()
        
        return task
    
    @staticmethod
    async def enqueue_image_task(task_id: int, user_telegram_id: int, image_file_id: str):
        """Поставить задачу обработки изображения в очередь ARQ"""
        redis = await create_pool(get_redis_settings())
        
        await redis.enqueue_job(
            "process_image_task",
            task_id,
            user_telegram_id,
            image_file_id
        )
        
        logger.info(f"Image task enqueued: task_id={task_id}")
    
    @staticmethod
    async def enqueue_video_task(task_id: int, user_telegram_id: int, video_file_id: str):
        """Поставить задачу обработки видео в очередь ARQ"""
        redis = await create_pool(get_redis_settings())
        
        await redis.enqueue_job(
            "process_video_task",
            task_id,
            user_telegram_id,
            video_file_id
        )
        
        logger.info(f"Video task enqueued: task_id={task_id}")