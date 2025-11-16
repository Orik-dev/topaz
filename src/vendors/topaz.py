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

    # ========== IMAGE API - СИНХРОННЫЕ ENDPOINT'Ы ==========

    async def enhance_image(
        self,
        image_data: bytes,
        model: str = "Standard V2",
        output_format: str = "jpeg",
        **params
    ) -> bytes:
        """
        Улучшить фото (синхронный endpoint)
        Документация: /enhance
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        # Добавляем параметры
        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/enhance",
                data=form
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz enhance error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка улучшения фото (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz enhance network error: {e}")
            raise TopazAPIError("Ошибка сети при обработке фото")

    async def sharpen_image(
        self,
        image_data: bytes,
        model: str = "Standard",
        output_format: str = "jpeg",
        **params
    ) -> bytes:
        """
        Убрать размытие (синхронный endpoint)
        Документация: /sharpen
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/sharpen",
                data=form
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz sharpen error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка резкости (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz sharpen network error: {e}")
            raise TopazAPIError("Ошибка сети при обработке фото")

    async def denoise_image(
        self,
        image_data: bytes,
        model: str = "Normal",
        output_format: str = "jpeg",
        **params
    ) -> bytes:
        """
        Шумоподавление (синхронный endpoint)
        Документация: /denoise
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/denoise",
                data=form
            ) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz denoise error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка шумоподавления (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz denoise network error: {e}")
            raise TopazAPIError("Ошибка сети при обработке фото")

    # ========== IMAGE API - АСИНХРОННЫЕ ENDPOINT'Ы (GENERATIVE) ==========

    async def enhance_image_async(
        self,
        image_data: bytes,
        model: str = "Redefine",
        output_format: str = "jpeg",
        **params
    ) -> str:
        """
        Улучшить фото (асинхронный generative endpoint)
        Документация: /enhance-gen/async
        Возвращает process_id для polling
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/enhance-gen/async",
                data=form
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("process_id")
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz enhance-gen error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка AI-улучшения (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz enhance-gen network error: {e}")
            raise TopazAPIError("Ошибка сети при AI-улучшении")

    async def sharpen_image_async(
        self,
        image_data: bytes,
        model: str = "Super Focus",
        output_format: str = "jpeg",
        **params
    ) -> str:
        """
        Резкость AI (асинхронный generative endpoint)
        Документация: /sharpen-gen/async
        Возвращает process_id для polling
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/sharpen-gen/async",
                data=form
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("process_id")
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz sharpen-gen error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка AI-резкости (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz sharpen-gen network error: {e}")
            raise TopazAPIError("Ошибка сети при AI-резкости")

    async def restore_image_async(
        self,
        image_data: bytes,
        model: str = "Dust-Scratch",
        output_format: str = "jpeg",
        **params
    ) -> str:
        """
        Восстановление фото (асинхронный generative endpoint)
        Документация: /restore-gen/async
        Возвращает process_id для polling
        """
        session = await self._get_session()

        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)

        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))

        try:
            async with session.post(
                f"{self.image_url}/restore-gen/async",
                data=form
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("process_id")
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz restore-gen error: {response.status} - {error_text}")
                    raise TopazAPIError(f"Ошибка восстановления (код {response.status})")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz restore-gen network error: {e}")
            raise TopazAPIError("Ошибка сети при восстановлении")

    async def get_image_status(self, process_id: str) -> Dict[str, Any]:
        """
        Получить статус обработки фото (для async endpoint'ов)
        Документация: /status/{process_id}
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.image_url}/status/{process_id}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz image status error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка получения статуса")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz image status network error: {e}")
            raise TopazAPIError("Ошибка сети при получении статуса")

    async def download_image_output(self, process_id: str) -> bytes:
        """
        Скачать результат обработки фото (для async endpoint'ов)
        Документация: /download/output/{process_id}
        """
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.image_url}/download/output/{process_id}"
            ) as response:
                if response.status == 200:
                    # Получаем signed URL
                    data = await response.json()
                    download_url = data.get("url")
                    
                    # Скачиваем по signed URL
                    async with session.get(download_url) as download_response:
                        if download_response.status == 200:
                            return await download_response.read()
                        else:
                            raise TopazAPIError("Ошибка скачивания результата")
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz download error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка получения ссылки на скачивание")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz download network error: {e}")
            raise TopazAPIError("Ошибка сети при скачивании")

    # ========== VIDEO API ==========

    async def create_video_request(
        self,
        source: Dict[str, Any],
        output: Dict[str, Any],
        filters: list
    ) -> Dict[str, Any]:
        """
        Создать запрос на обработку видео (Шаг 1)
        Документация: POST /video/
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
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"Topaz video create error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка создания запроса видео")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz video create network error: {e}")
            raise TopazAPIError("Ошибка сети при создании запроса")

    async def accept_video_request(self, request_id: str) -> Dict[str, Any]:
        """
        Принять запрос и получить URL для загрузки (Шаг 2)
        Документация: PATCH /video/{requestId}/accept
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
                    logger.error(f"Topaz video accept error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка принятия запроса")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz video accept network error: {e}")
            raise TopazAPIError("Ошибка сети при принятии запроса")

    async def upload_video(self, upload_url: str, video_data: bytes) -> str:
        """
        Загрузить видео на S3 (Шаг 3)
        Возвращает ETag
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
        Документация: PATCH /video/{requestId}/complete-upload
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
                    logger.error(f"Topaz video complete error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка завершения загрузки")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz video complete network error: {e}")
            raise TopazAPIError("Ошибка сети при завершении загрузки")

    async def get_video_status(self, request_id: str) -> Dict[str, Any]:
        """
        Получить статус обработки видео (Polling)
        Документация: GET /video/{requestId}/status
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
                    logger.error(f"Topaz video status error: {response.status} - {error_text}")
                    raise TopazAPIError("Ошибка получения статуса видео")

        except aiohttp.ClientError as e:
            logger.error(f"Topaz video status network error: {e}")
            raise TopazAPIError("Ошибка сети при получении статуса")


# Singleton instance
topaz_client = TopazClient()