from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_PATH: str = "/tg/webhook"
    WEBHOOK_SECRET: str

    DB_HOST: str
    DB_PORT: int = 3306
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    TOPAZ_API_KEY: str
    TOPAZ_IMAGE_API_URL: str = "https://api.topazlabs.com/image/v1"
    TOPAZ_VIDEO_API_URL: str = "https://api.topazlabs.com/video"

    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    YOOKASSA_RETURN_URL: str
    DEFAULT_RECEIPT_EMAIL: str = "[email protected]"

    STARS_CONVERSION_RATE: float = 2.0
    SUPPORT_USERNAME: str = "guardGpt"
    ADMIN_IDS: str = ""

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def admin_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()