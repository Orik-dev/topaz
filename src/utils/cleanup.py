"""Cleanup utilities for temp files and old data."""
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

from src.core.config import config
from src.core.logging import logger


async def cleanup_temp_files():
    """Clean up old temporary files."""
    temp_dir = Path(config.TEMP_DIR)
    
    if not temp_dir.exists():
        return
    
    cutoff_time = datetime.utcnow() - timedelta(hours=config.CLEANUP_INTERVAL_HOURS)
    deleted_count = 0
    freed_space = 0
    
    for file_path in temp_dir.rglob("*"):
        if not file_path.is_file():
            continue
        
        # Check file age
        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        if file_time < cutoff_time:
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                deleted_count += 1
                freed_space += file_size
                logger.debug(f"Deleted temp file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete temp file {file_path}: {e}")
    
    if deleted_count > 0:
        logger.info(
            f"Cleanup: deleted {deleted_count} files, "
            f"freed {freed_space / 1024 / 1024:.2f} MB"
        )


async def cleanup_old_jobs():
    """Clean up old completed/failed jobs from database."""
    from src.db.engine import get_session
    from src.db.models import Job
    from sqlalchemy import delete
    
    cutoff_time = datetime.utcnow() - timedelta(days=30)  # Keep 30 days
    
    async with get_session() as session:
        stmt = delete(Job).where(
            Job.created_at < cutoff_time,
            Job.status.in_(["completed", "failed"])
        )
        
        result = await session.execute(stmt)
        await session.commit()
        
        deleted_count = result.rowcount
        
        if deleted_count > 0:
            logger.info(f"Cleanup: deleted {deleted_count} old jobs")


async def cleanup_worker():
    """Background worker for periodic cleanup."""
    while True:
        try:
            await cleanup_temp_files()
            await cleanup_old_jobs()
        except Exception as e:
            logger.error(f"Cleanup worker error: {e}")
        
        # Run every hour
        await asyncio.sleep(3600)


def start_cleanup_worker():
    """Start cleanup worker task."""
    asyncio.create_task(cleanup_worker())
    logger.info("Cleanup worker started")