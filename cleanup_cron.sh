#!/bin/bash
# Cleanup temp files every 10 minutes
# Add to crontab: */10 * * * * /path/to/cleanup_cron.sh >> /var/log/topaz_cleanup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[$(date)] Starting cleanup..."

docker exec topaz_bot python3 -c "
import sys
sys.path.insert(0, '/app')
from src.utils.file_manager import DiskManager
DiskManager.cleanup_old_files('/app/temp_inputs', 3600)
print('Cleanup completed')
" || echo "[$(date)] Cleanup failed"

echo "[$(date)] Cleanup finished"