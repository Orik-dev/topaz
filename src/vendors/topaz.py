import aiohttp
import asyncio
from typing import Optional, Dict, Any
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TopazAPIError(Exception):
    """Topaz API exception"""
    pass


class TopazClient:
    def __init__(self):
        self.api_key = settings.TOPAZ_API_KEY
        self.image_url = settings.TOPAZ_IMAGE_API_URL
        self.video_url = settings.TOPAZ_VIDEO_API_URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить HTTP сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"X-API-Key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=600)
            )
        return self.session

    async def close(self):
        """Закрыть сессию"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def enhance_image(
        self,
        image_data: bytes,
        model: str = "Standard V2",
        output_format: str = "jpeg",
        **params
    ) -> bytes:
        """
        Улучшить фото (синхронный API)
        Документация: https://developer.topazlabs.com/image-api/introduction
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        # Добавляем параметры модели
        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value))

        try:
            async with session.post(
                f"{self.image_url}/enhance",
                data=form
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz Image API error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка обработки фото. Код: {response.status}")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz Image API network error: {e}")
            raise TopazAPIError("Ошибка сети при обработке фото")

    async def create_video_request(
        self,
        source: Dict[str, Any],
        output: Dict[str, Any],
        filters: list
    ) -> Dict[str, Any]:
        """
        Создать запрос на обработку видео (Шаг 1)
        Документация: https://developer.topazlabs.com/video-api/api-walkthrough
        """
        session = await self._get_session()

        payload = {
            "source": source,
            "output": output,
            "filters": filters
        }

        try:
            async with session.post(
                f"{self.video_url}/",
                json=payload
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz Video create error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка создания запроса видео")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz Video create network error: {e}")
            raise TopazAPIError("Ошибка сети при создании запроса")

    async def accept_video_request(self, request_id: str) -> Dict[str, Any]:
        """
        Принять запрос и получить URL для загрузки (Шаг 2)
        """
        session = await self._get_session()

        try:
            async with session.patch(
                f"{self.video_url}/{request_id}/accept"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz Video accept error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка принятия запроса")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz Video accept network error: {e}")
            raise TopazAPIError("Ошибка сети при принятии запроса")

    async def upload_video(self, upload_url: str, video_data: bytes) -> str:
        """
        Загрузить видео на S3 (Шаг 3)
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    upload_url,
                    data=video_data,
                    headers={"Content-Type": "video/mp4"}
                ) as response:
                    if response.status in [200, 201]:
                        etag = response.headers.get('ETag', '').strip('"')
                        return etag
                    else:
                        error_text = await response.text()
                        logger.error(f"S3 upload error: {response.status} - {error_text}")
                        raise TopazAPIError("Ошибка загрузки видео")

        except aiohttp.ClientError as e:
            logger.error(f"S3 upload network error: {e}")
            raise TopazAPIError("Ошибка сети при загрузке видео")

    async def complete_video_upload(
        self,
        request_id: str,
        upload_results: list
    ) -> Dict[str, Any]:
        """
        Завершить загрузку и начать обработку (Шаг 4)
        """
        session = await self._get_session()

        payload = {"uploadResults": upload_results}

        try:
            async with session.patch(
                f"{self.video_url}/{request_id}/complete-upload",
                json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz Video complete error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка завершения загрузки")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz Video complete network error: {e}")
            raise TopazAPIError("Ошибка сети при завершении загрузки")

    async def get_video_status(self, request_id: str) -> Dict[str, Any]:
        """
        Получить статус обработки видео (Polling)
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.video_url}/{request_id}/status"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz Video status error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка получения статуса")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz Video status network error: {e}")
            raise TopazAPIError("Ошибка сети при получении статуса")


# Singleton instance
topaz_client = TopazClient()