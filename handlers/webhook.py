"""Webhook handlers for Topaz API callbacks."""
import hmac
import hashlib
from aiogram import Router
from aiohttp import web
from aiogram.types import Update

from src.db.engine import get_session
from src.services.jobs import get_job, update_job_status
from src.services.users import update_balance
from src.core.config import config
from src.core.logging import logger

router = Router(name="webhook")


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify webhook signature."""
    if not config.WEBHOOK_SECRET:
        return True  # No signature verification if secret not set
    
    expected_signature = hmac.new(
        config.WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


async def handle_topaz_webhook(request: web.Request):
    """Handle Topaz API webhook."""
    # Get signature
    signature = request.headers.get("X-Topaz-Signature", "")
    
    # Get payload
    payload = await request.read()
    
    # Verify signature
    if not verify_webhook_signature(payload, signature):
        logger.warning(f"Invalid webhook signature from {request.remote}")
        return web.Response(status=401, text="Invalid signature")
    
    # Parse JSON
    try:
        import json
        data = json.loads(payload)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        return web.Response(status=400, text="Invalid JSON")
    
    # Get job info
    topaz_job_id = data.get("job_id")
    status = data.get("status")
    output_url = data.get("output", {}).get("url")
    error = data.get("error")
    
    if not topaz_job_id:
        logger.error("Webhook missing job_id")
        return web.Response(status=400, text="Missing job_id")
    
    # Find our job
    async with get_session() as session:
        from sqlalchemy import select
        from src.db.models import Job
        
        result = await session.execute(
            select(Job).where(Job.topaz_job_id == topaz_job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            logger.warning(f"Job not found for Topaz job {topaz_job_id}")
            return web.Response(status=404, text="Job not found")
        
        # Update job status
        if status == "completed":
            await update_job_status(session, job.id, "completed", output_file_id=output_url)
            logger.info(f"Job {job.id} completed via webhook")
            
            # Send notification to user
            from aiogram import Bot
            bot = request.app["bot"]
            
            try:
                # Download and send result
                from src.vendors.topaz import TopazClient
                async with TopazClient(config.TOPAZ_API_KEY) as topaz:
                    result_data = await topaz.download_result(output_url)
                
                from pathlib import Path
                from aiogram.types import FSInputFile
                
                result_path = Path(config.TEMP_DIR) / f"webhook_result_{job.id}.{'jpg' if job.type == 'image' else 'mp4'}"
                with open(result_path, "wb") as f:
                    f.write(result_data)
                
                if job.type == "image":
                    await bot.send_photo(
                        job.telegram_id,
                        FSInputFile(result_path),
                        caption=f"✅ <b>Обработка завершена!</b>\n\n💰 Потрачено: {job.credits_cost} кредитов",
                        parse_mode="HTML"
                    )
                else:
                    await bot.send_video(
                        job.telegram_id,
                        FSInputFile(result_path),
                        caption=f"✅ <b>Обработка завершена!</b>\n\n💰 Потрачено: {job.credits_cost} кредитов",
                        parse_mode="HTML"
                    )
                
                result_path.unlink(missing_ok=True)
                
            except Exception as e:
                logger.error(f"Failed to send webhook result to user: {e}")
        
        elif status == "failed":
            await update_job_status(session, job.id, "failed", error_message=error)
            logger.error(f"Job {job.id} failed via webhook: {error}")
            
            # Return credits
            await update_balance(session, job.telegram_id, job.credits_cost)
            
            # Notify user
            from aiogram import Bot
            bot = request.app["bot"]
            
            try:
                await bot.send_message(
                    job.telegram_id,
                    f"❌ <b>Ошибка обработки!</b>\n\n"
                    f"Причина: {error or 'Unknown error'}\n\n"
                    f"💰 Кредиты возвращены: {job.credits_cost}",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send webhook error to user: {e}")
    
    return web.Response(status=200, text="OK")


def setup_webhook_routes(app: web.Application):
    """Setup webhook routes."""
    app.router.add_post("/webhook/topaz", handle_topaz_webhook)