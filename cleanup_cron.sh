#!/bin/bash
# Запускать каждые 10 минут через crontab: */10 * * * *

docker exec topaz_bot python3 << 'EOF'
import sys
sys.path.insert(0, '/app')

from src.utils.file_manager import DiskManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    DiskManager.cleanup_old_files("/app/temp_inputs", max_age_seconds=3600)
    logger.info("Cleanup completed")
except Exception as e:
    logger.error(f"Cleanup failed: {e}")
EOF