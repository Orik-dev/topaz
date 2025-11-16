"""Topaz Labs API client."""
import aiohttp
import asyncio
from typing import Optional, Dict, Any, BinaryIO
from dataclasses import dataclass

from src.core.config import config
from src.core.logging import logger


@dataclass
class TopazImageJob:
    """Topaz image processing job."""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    output_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class TopazVideoJob:
    """Topaz video processing job."""
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: float = 0.0  # 0-100
    output_url: Optional[str] = None
    error: Optional[str] = None


class TopazAPIError(Exception):
    """Topaz API error."""
    pass


class TopazClient:
    """Topaz Labs API client with rate limiting and retries."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.image_api_url = config.TOPAZ_IMAGE_API_URL
        self.video_api_url = config.TOPAZ_VIDEO_API_URL
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_JOBS)
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms between requests
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=300)  # 5 minutes
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    async def _request(
        self,
        method: str,
        url: str,
        json: Optional[Dict] = None,
        data: Optional[Any] = None,
        retries: int = 3,
    ) -> Dict[str, Any]:
        """Make HTTP request with retries."""
        if not self.session:
            raise TopazAPIError("Session not initialized")
        
        async with self._semaphore:
            await self._rate_limit()
            
            for attempt in range(retries):
                try:
                    async with self.session.request(
                        method,
                        url,
                        json=json,
                        data=data,
                    ) as response:
                        response_data = await response.json()
                        
                        if response.status == 200:
                            return response_data
                        
                        elif response.status == 429:  # Rate limit
                            retry_after = int(response.headers.get("Retry-After", 5))
                            logger.warning(f"Rate limited, retrying after {retry_after}s")
                            await asyncio.sleep(retry_after)
                            continue
                        
                        elif response.status >= 500:  # Server error
                            if attempt < retries - 1:
                                wait_time = 2 ** attempt
                                logger.warning(f"Server error, retrying after {wait_time}s")
                                await asyncio.sleep(wait_time)
                                continue
                        
                        # Other errors
                        error_msg = response_data.get("error", f"HTTP {response.status}")
                        raise TopazAPIError(f"API error: {error_msg}")
                
                except aiohttp.ClientError as e:
                    if attempt < retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Request failed: {e}, retrying after {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    raise TopazAPIError(f"Request failed: {e}")
        
        raise TopazAPIError("Max retries exceeded")
    
    # ==================== IMAGE API ====================
    
    async def process_image(
        self,
        image_data: bytes,
        model: str,
        webhook_url: Optional[str] = None,
        **params
    ) -> TopazImageJob:
        """
        Обработать изображение.
        
        Args:
            image_data: Бинарные данные изображения
            model: Модель (face-recovery-v1, photo-enhance-v1, etc.)
            webhook_url: URL для вебхука при завершении
            **params: Дополнительные параметры модели
        """
        # Upload image
        upload_url = await self._get_image_upload_url()
        image_url = await self._upload_file(upload_url, image_data, "image")
        
        # Create job
        payload = {
            "model": model,
            "input": {"url": image_url},
            **params
        }
        
        if webhook_url:
            payload["webhook_url"] = webhook_url
        
        response = await self._request(
            "POST",
            f"{self.image_api_url}/jobs",
            json=payload
        )
        
        return TopazImageJob(
            job_id=response["id"],
            status=response["status"],
        )
    
    async def get_image_job(self, job_id: str) -> TopazImageJob:
        """Получить статус задачи обработки изображения."""
        response = await self._request(
            "GET",
            f"{self.image_api_url}/jobs/{job_id}"
        )
        
        return TopazImageJob(
            job_id=response["id"],
            status=response["status"],
            output_url=response.get("output", {}).get("url"),
            error=response.get("error"),
        )
    
    async def _get_image_upload_url(self) -> str:
        """Получить URL для загрузки изображения."""
        response = await self._request(
            "POST",
            f"{self.image_api_url}/upload"
        )
        return response["upload_url"]
    
    # ==================== VIDEO API ====================
    
    async def process_video(
        self,
        video_data: bytes,
        model: str,
        webhook_url: Optional[str] = None,
        **params
    ) -> TopazVideoJob:
        """
        Обработать видео.
        
        Args:
            video_data: Бинарные данные видео
            model: Модель (enhance-v3, iris-v1, proteus-v1)
            webhook_url: URL для вебхука при завершении
            **params: Дополнительные параметры модели
        """
        # Upload video
        upload_url = await self._get_video_upload_url()
        video_url = await self._upload_file(upload_url, video_data, "video")
        
        # Create job
        payload = {
            "model": model,
            "input": {"url": video_url},
            **params
        }
        
        if webhook_url:
            payload["webhook_url"] = webhook_url
        
        response = await self._request(
            "POST",
            f"{self.video_api_url}/jobs",
            json=payload
        )
        
        return TopazVideoJob(
            job_id=response["id"],
            status=response["status"],
        )
    
    async def get_video_job(self, job_id: str) -> TopazVideoJob:
        """Получить статус задачи обработки видео."""
        response = await self._request(
            "GET",
            f"{self.video_api_url}/jobs/{job_id}"
        )
        
        return TopazVideoJob(
            job_id=response["id"],
            status=response["status"],
            progress=response.get("progress", 0.0),
            output_url=response.get("output", {}).get("url"),
            error=response.get("error"),
        )
    
    async def _get_video_upload_url(self) -> str:
        """Получить URL для загрузки видео."""
        response = await self._request(
            "POST",
            f"{self.video_api_url}/upload"
        )
        return response["upload_url"]
    
    # ==================== COMMON ====================
    
    async def _upload_file(self, upload_url: str, file_data: bytes, file_type: str) -> str:
        """Загрузить файл на сервер Topaz."""
        if not self.session:
            raise TopazAPIError("Session not initialized")
        
        content_type = "image/jpeg" if file_type == "image" else "video/mp4"
        
        async with self.session.put(
            upload_url,
            data=file_data,
            headers={"Content-Type": content_type}
        ) as response:
            if response.status != 200:
                raise TopazAPIError(f"Upload failed: HTTP {response.status}")
        
        # Extract file URL from upload URL (remove query params)
        file_url = upload_url.split("?")[0]
        return file_url
    
    async def download_result(self, url: str) -> bytes:
        """Скачать результат обработки."""
        if not self.session:
            raise TopazAPIError("Session not initialized")
        
        async with self.session.get(url) as response:
            if response.status != 200:
                raise TopazAPIError(f"Download failed: HTTP {response.status}")
            return await response.read()