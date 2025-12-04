import aiohttp
import asyncio
from typing import Optional, Dict, Any
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TopazAPIError(Exception):
    """Topaz API exception"""
    def __init__(self, message: str, status_code: int = None, user_message: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.user_message = user_message or message


class TopazClient:
    def __init__(self):
        self.api_key = settings.TOPAZ_API_KEY
        self.image_url = settings.TOPAZ_IMAGE_API_URL
        self.video_url = settings.TOPAZ_VIDEO_API_URL
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"X-API-Key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=600)
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    def _handle_error(self, status: int, text: str, operation: str):
        """Обработка ошибок согласно документации"""
        if status == 400:
            raise TopazAPIError(
                f"{operation}: Bad Request - {text}",
                status,
                "Неверные параметры запроса"
            )
        elif status == 401:
            raise TopazAPIError(
                f"{operation}: Unauthorized - {text}",
                status,
                "Ошибка авторизации API"
            )
        elif status == 403:
            raise TopazAPIError(
                f"{operation}: Forbidden - {text}",
                status,
                "Доступ запрещен"
            )
        elif status == 404:
            raise TopazAPIError(
                f"{operation}: Not Found - {text}",
                status,
                "Запрос не найден"
            )
        elif status == 503:
            raise TopazAPIError(
                f"{operation}: Service Unavailable - {text}",
                status,
                "Сервис временно недоступен"
            )
        elif status >= 500:
            raise TopazAPIError(
                f"{operation}: Server Error {status} - {text}",
                status,
                "Ошибка сервера обработки"
            )
        else:
            raise TopazAPIError(
                f"{operation}: Error {status} - {text}",
                status,
                "Ошибка обработки"
            )

    # IMAGE API
    async def enhance_image(self, image_data: bytes, model: str = "Standard V2", output_format: str = "jpeg", **params) -> bytes:
        session = await self._get_session()
        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)
        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))
        
        try:
            async with session.post(f"{self.image_url}/enhance", data=form) as response:
                if response.status == 200:
                    return await response.read()
                text = await response.text()
                self._handle_error(response.status, text, "Enhance image")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    async def sharpen_image(self, image_data: bytes, model: str = "Standard", output_format: str = "jpeg", **params) -> bytes:
        session = await self._get_session()
        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)
        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))
        
        try:
            async with session.post(f"{self.image_url}/sharpen", data=form) as response:
                if response.status == 200:
                    return await response.read()
                text = await response.text()
                self._handle_error(response.status, text, "Sharpen image")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    async def denoise_image(self, image_data: bytes, model: str = "Normal", output_format: str = "jpeg", **params) -> bytes:
        session = await self._get_session()
        form = aiohttp.FormData()
        form.add_field('image', image_data, filename='image.jpg', content_type='image/jpeg')
        form.add_field('model', model)
        form.add_field('output_format', output_format)
        for key, value in params.items():
            if value is not None:
                form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))
        
        try:
            async with session.post(f"{self.image_url}/denoise", data=form) as response:
                if response.status == 200:
                    return await response.read()
                text = await response.text()
                self._handle_error(response.status, text, "Denoise image")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    # VIDEO API
    async def create_video_request(self, source: Dict, filters: list, output: Dict) -> Dict:
        session = await self._get_session()
        payload = {"source": source, "filters": filters, "output": output}
        
        try:
            async with session.post(f"{self.video_url}/", json=payload) as response:
                if response.status in [200, 201]:
                    return await response.json()
                text = await response.text()
                logger.error(f"Create video request error {response.status}: {text}")
                self._handle_error(response.status, text, "Create video request")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    async def accept_video_request(self, request_id: str) -> Dict:
        session = await self._get_session()
        try:
            async with session.patch(f"{self.video_url}/{request_id}/accept") as response:
                if response.status == 200:
                    return await response.json()
                text = await response.text()
                self._handle_error(response.status, text, "Accept video request")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    async def upload_video_to_url(self, upload_url: str, video_data: bytes) -> str:
        try:
            async with aiohttp.ClientSession() as temp_session:
                async with temp_session.put(upload_url, data=video_data, headers={"Content-Type": "video/mp4"}) as response:
                    if response.status in [200, 201]:
                        return response.headers.get('ETag', '').strip('"')
                    text = await response.text()
                    raise TopazAPIError(
                        f"Upload failed {response.status}: {text}",
                        response.status,
                        "Ошибка загрузки видео"
                    )
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Upload network error: {e}", user_message="Ошибка загрузки видео")

    async def complete_video_upload(self, request_id: str, upload_results: list) -> Dict:
        session = await self._get_session()
        try:
            async with session.patch(f"{self.video_url}/{request_id}/complete-upload", json={"uploadResults": upload_results}) as response:
                if response.status == 200:
                    return await response.json()
                text = await response.text()
                self._handle_error(response.status, text, "Complete video upload")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка сети")

    async def get_video_status(self, request_id: str) -> Dict:
        session = await self._get_session()
        try:
            async with session.get(f"{self.video_url}/{request_id}/status") as response:
                if response.status == 200:
                    return await response.json()
                text = await response.text()
                self._handle_error(response.status, text, "Get video status")
        except aiohttp.ClientError as e:
            raise TopazAPIError(f"Network error: {e}", user_message="Ошибка проверки статуса")

    async def cancel_video_request(self, request_id: str) -> Dict:
        """Отмена запроса с возвратом кредитов"""
        session = await self._get_session()
        try:
            async with session.delete(f"{self.video_url}/{request_id}") as response:
                if response.status in [200, 204]:
                    if response.status == 200:
                        return await response.json()
                    return {"message": "Canceled"}
                text = await response.text()
                logger.warning(f"Cancel video warning {response.status}: {text}")
                return {"message": text}
        except Exception as e:
            logger.error(f"Cancel video error: {e}")
            return {"message": "Cancel failed"}


topaz_client = TopazClient()