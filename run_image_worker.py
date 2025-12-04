#!/usr/bin/env python3
"""
Прямой запуск ARQ image worker
Обходит проблему с uvloop event loop в Python 3.11+
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    from arq import Worker
    from src.workers.settings import get_redis_settings
    from src.workers.image_worker import WorkerSettings
    
    logger.info("✅ Starting image worker...")
    
    worker = Worker(
        functions=WorkerSettings.functions,
        redis_settings=get_redis_settings(),
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        queue_name=WorkerSettings.queue_name,
    )
    
    await worker.main()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Image worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Image worker error: {e}", exc_info=True)
        raise