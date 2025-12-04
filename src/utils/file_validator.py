import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class FileValidator:
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_IMAGE_SIZE = 20 * 1024 * 1024   # 20 MB
    MAX_VIDEO_DURATION = 300  # 5 минут
    MIN_VIDEO_DURATION = 1
    
    @staticmethod
    def validate_image_size(file_size: int) -> Tuple[bool, Optional[str]]:
        """Валидация размера изображения"""
        if file_size > FileValidator.MAX_IMAGE_SIZE:
            max_mb = FileValidator.MAX_IMAGE_SIZE // 1024 // 1024
            return False, f"Изображение слишком большое (макс. {max_mb} МБ)"
        return True, None
    
    @staticmethod
    def validate_video_size(file_size: int) -> Tuple[bool, Optional[str]]:
        """Валидация размера видео"""
        if file_size > FileValidator.MAX_VIDEO_SIZE:
            max_mb = FileValidator.MAX_VIDEO_SIZE // 1024 // 1024
            return False, f"Видео слишком большое (макс. {max_mb} МБ)"
        return True, None
    
    @staticmethod
    def validate_video_duration(duration: float) -> Tuple[bool, Optional[str]]:
        """Валидация длительности видео"""
        if duration < FileValidator.MIN_VIDEO_DURATION:
            return False, "Видео слишком короткое (мин. 1 сек)"
        
        if duration > FileValidator.MAX_VIDEO_DURATION:
            max_min = FileValidator.MAX_VIDEO_DURATION // 60
            return False, f"Видео слишком длинное (макс. {max_min} мин)"
        
        return True, None


file_validator = FileValidator()