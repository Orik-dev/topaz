"""Application configuration."""
import os
from dataclasses import dataclass
from typing import List


@dataclass
class Config:
    """Application configuration."""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: List[int] = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    
    # Topaz Labs API
    TOPAZ_API_KEY: str = os.getenv("TOPAZ_API_KEY", "4b7ae8b8-cb47-4d53-9b97-189d72033957")
    TOPAZ_IMAGE_API_URL: str = "https://api.topazlabs.com/v1/image"
    TOPAZ_VIDEO_API_URL: str = "https://api.topazlabs.com/v1/video"
    TOPAZ_WEBHOOK_URL: str = os.getenv("TOPAZ_WEBHOOK_URL", "")  # Ваш публичный URL для вебхуков
    
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "topaz_bot")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "secure_password_here")
    DB_NAME: str = os.getenv("DB_NAME", "topaz_bot")
    
    @property
    def DATABASE_URL(self) -> str:
        """MySQL connection URL."""
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Redis (для кэша и очередей)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    @property
    def REDIS_URL(self) -> str:
        """Redis connection URL."""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # File Storage
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/topaz_bot")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
    CLEANUP_INTERVAL_HOURS: int = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))
    
    # Rate Limiting
    MAX_CONCURRENT_JOBS: int = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
    MAX_JOBS_PER_USER: int = int(os.getenv("MAX_JOBS_PER_USER", "3"))
    
    # Payment (YooKassa)
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() == "true"
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/bot.log")
    
    # Security
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")  # Секрет для подписи вебхуков
    
    def __post_init__(self):
        """Validate configuration."""
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not self.ADMIN_IDS:
            raise ValueError("ADMIN_IDS is required")
        if not self.TOPAZ_API_KEY:
            raise ValueError("TOPAZ_API_KEY is required")


# Global config instance
config = Config()