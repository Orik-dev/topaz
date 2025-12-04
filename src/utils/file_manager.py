import os
import shutil
import logging
from pathlib import Path
from typing import Optional
import tempfile

logger = logging.getLogger(__name__)

MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
MAX_IMAGE_SIZE = 20 * 1024 * 1024        # 20 MB
MIN_FREE_DISK_GB = 10  # ✅ Увеличено для больших видео


class DiskManager:
    @staticmethod
    def check_disk_space() -> bool:
        """Проверка свободного места"""
        try:
            stat = shutil.disk_usage("/app")
            free_gb = stat.free / (1024**3)
            if free_gb < MIN_FREE_DISK_GB:
                logger.critical(f"Low disk space: {free_gb:.1f} GB free")
                return False
            return True
        except Exception as e:
            logger.error(f"Disk check error: {e}")
            return True
    
    @staticmethod
    def save_temp_file(data: bytes, suffix: str) -> Optional[str]:
        """Безопасное сохранение во временный файл"""
        if not DiskManager.check_disk_space():
            raise IOError("Insufficient disk space")
        
        temp_dir = Path("/app/temp_inputs")
        temp_dir.mkdir(exist_ok=True)
        
        fd, path = tempfile.mkstemp(suffix=suffix, dir=str(temp_dir))
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            return path
        except Exception as e:
            try:
                os.unlink(path)
            except:
                pass
            raise e
    
    @staticmethod
    def cleanup_file(path: Optional[str]):
        """Безопасное удаление файла"""
        if path and os.path.exists(path):
            try:
                os.unlink(path)
                logger.debug(f"Cleaned up: {path}")
            except Exception as e:
                logger.warning(f"Cleanup failed {path}: {e}")
    
    @staticmethod
    def cleanup_old_files(directory: str, max_age_seconds: int = 3600):
        """Очистка старых файлов"""
        import time
        try:
            temp_dir = Path(directory)
            if not temp_dir.exists():
                return
            
            now = time.time()
            deleted = 0
            freed_mb = 0
            
            for file_path in temp_dir.glob("*"):
                if file_path.is_file():
                    age = now - file_path.stat().st_mtime
                    if age > max_age_seconds:
                        try:
                            size_mb = file_path.stat().st_size / 1024 / 1024
                            file_path.unlink()
                            deleted += 1
                            freed_mb += size_mb
                        except Exception as e:
                            logger.warning(f"Failed to delete {file_path}: {e}")
            
            if deleted > 0:
                logger.info(f"Cleaned {deleted} files ({freed_mb:.1f} MB) from {directory}")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


disk_manager = DiskManager()