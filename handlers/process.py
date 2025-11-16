"""Photo and video processing handlers."""
import os
import asyncio
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image
import io

from src.db.engine import get_session
from src.services.users import get_balance, update_balance
from src.services.jobs import create_job, update_job_status
from src.services.pricing import calculate_image_cost, calculate_video_cost
from src.vendors.topaz import TopazClient, TopazAPIError
from src.core.config import config
from src.core.logging import logger

router = Router(name="process")


class ProcessState(StatesGroup):
    """Processing states."""
    waiting_for_model = State()
    processing = State()


# Image models
IMAGE_MODELS = {
    "face-recovery-v1": "👤 Face Recovery - восстановление лиц",
    "photo-enhance-v1": "✨ Photo Enhance - улучшение фото",
    "denoise-v1": "🔇 Denoise - удаление шума",
    "sharpen-v1": "🔪 Sharpen - повышение резкости",
    "upscale-v1": "🔍 Upscale - увеличение",
}

# Video models
VIDEO_MODELS = {
    "enhance-v3": "✨ Enhance V3 - улучшение",
    "iris-v1": "🎞 Iris V1 - интерполяция",
    "proteus-v1": "⚡ Proteus V1 - макс. качество",
}


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Handle photo upload."""
    # Get largest photo
    photo = message.photo[-1]
    
    # Check file size (max 100MB)
    if photo.file_size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(
            f"❌ Файл слишком большой!\n"
            f"Максимальный размер: {config.MAX_FILE_SIZE_MB}MB"
        )
        return
    
    # Save file info to state
    await state.update_data(
        file_id=photo.file_id,
        file_size=photo.file_size,
        file_type="image",
        width=photo.width,
        height=photo.height,
    )
    
    # Calculate megapixels
    megapixels = (photo.width * photo.height) / 1_000_000
    
    # Show model selection
    keyboard_buttons = []
    for model_id, model_name in IMAGE_MODELS.items():
        cost = calculate_image_cost(model_id, megapixels)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{model_name} ({cost} кредитов)",
                callback_data=f"model_{model_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"📸 <b>Фото получено!</b>\n\n"
        f"📏 Разрешение: {photo.width}x{photo.height} ({megapixels:.1f} MP)\n"
        f"💾 Размер: {photo.file_size / 1024:.1f} KB\n\n"
        f"Выберите модель обработки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(ProcessState.waiting_for_model)


@router.message(F.video)
async def handle_video(message: Message, state: FSMContext):
    """Handle video upload."""
    video = message.video
    
    # Check file size
    if video.file_size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
        await message.answer(
            f"❌ Файл слишком большой!\n"
            f"Максимальный размер: {config.MAX_FILE_SIZE_MB}MB"
        )
        return
    
    # Save file info to state
    await state.update_data(
        file_id=video.file_id,
        file_size=video.file_size,
        file_type="video",
        duration=video.duration,
    )
    
    # Show model selection
    keyboard_buttons = []
    for model_id, model_name in VIDEO_MODELS.items():
        cost = calculate_video_cost(model_id, video.duration)
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{model_name} ({cost} кредитов)",
                callback_data=f"model_{model_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await message.answer(
        f"🎬 <b>Видео получено!</b>\n\n"
        f"⏱ Длительность: {video.duration}с\n"
        f"💾 Размер: {video.file_size / 1024 / 1024:.1f} MB\n\n"
        f"Выберите модель обработки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(ProcessState.waiting_for_model)


@router.callback_query(F.data.startswith("model_"), ProcessState.waiting_for_model)
async def process_file(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Process file with selected model."""
    model = callback.data.split("_", 1)[1]
    data = await state.get_data()
    
    file_type = data["file_type"]
    file_id = data["file_id"]
    file_size = data["file_size"]
    
    # Calculate cost
    if file_type == "image":
        megapixels = (data["width"] * data["height"]) / 1_000_000
        cost = calculate_image_cost(model, megapixels)
    else:
        cost = calculate_video_cost(model, data["duration"])
    
    # Check balance
    async with get_session() as session:
        balance = await get_balance(session, callback.from_user.id)
        
        if balance < cost:
            await callback.message.edit_text(
                f"❌ <b>Недостаточно кредитов!</b>\n\n"
                f"💳 Ваш баланс: {balance} кредитов\n"
                f"💰 Требуется: {cost} кредитов\n\n"
                f"Пополните баланс командой /balance",
                parse_mode="HTML"
            )
            await state.clear()
            return
        
        # Reserve credits (will be returned if processing fails)
        await update_balance(session, callback.from_user.id, -cost)
        
        # Create job
        job = await create_job(
            session,
            callback.from_user.id,
            file_type,
            model,
            cost,
            file_id,
            file_size,
        )
    
    await callback.message.edit_text(
        f"⏳ <b>Обработка началась...</b>\n\n"
        f"Это может занять несколько минут.\n"
        f"Я пришлю вам результат, когда обработка завершится.",
        parse_mode="HTML"
    )
    
    await state.clear()
    
    # Process in background
    asyncio.create_task(process_job_task(bot, job.id, file_id, model, file_type, cost))
    
    await callback.answer()


async def process_job_task(bot: Bot, job_id: str, file_id: str, model: str, file_type: str, cost: int):
    """Background task for processing."""
    try:
        # Download file
        file = await bot.get_file(file_id)
        file_path = Path(config.TEMP_DIR) / f"{job_id}_{file.file_path.split('/')[-1]}"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        await bot.download_file(file.file_path, file_path)
        
        # Read file
        with open(file_path, "rb") as f:
            file_data = f.read()
        
        # Process with Topaz
        async with TopazClient(config.TOPAZ_API_KEY) as topaz:
            if file_type == "image":
                topaz_job = await topaz.process_image(file_data, model)
            else:
                topaz_job = await topaz.process_video(file_data, model)
            
            # Update job
            async with get_session() as session:
                await update_job_status(session, job_id, "processing", topaz_job.job_id)
            
            # Poll for completion
            max_attempts = 300  # 5 minutes for images, longer for videos
            if file_type == "video":
                max_attempts = 1800  # 30 minutes for videos
            
            for _ in range(max_attempts):
                await asyncio.sleep(2)
                
                if file_type == "image":
                    topaz_job = await topaz.get_image_job(topaz_job.job_id)
                else:
                    topaz_job = await topaz.get_video_job(topaz_job.job_id)
                
                if topaz_job.status == "completed":
                    # Download result
                    result_data = await topaz.download_result(topaz_job.output_url)
                    
                    # Save result
                    result_path = Path(config.TEMP_DIR) / f"result_{job_id}.{'jpg' if file_type == 'image' else 'mp4'}"
                    with open(result_path, "wb") as f:
                        f.write(result_data)
                    
                    # Send to user
                    async with get_session() as session:
                        from src.services.jobs import get_job
                        job = await get_job(session, job_id)
                        
                        if file_type == "image":
                            sent_msg = await bot.send_photo(
                                job.telegram_id,
                                FSInputFile(result_path),
                                caption=f"✅ <b>Обработка завершена!</b>\n\n"
                                        f"🎨 Модель: {IMAGE_MODELS.get(model, model)}\n"
                                        f"💰 Потрачено: {cost} кредитов",
                                parse_mode="HTML"
                            )
                            output_file_id = sent_msg.photo[-1].file_id
                        else:
                            sent_msg = await bot.send_video(
                                job.telegram_id,
                                FSInputFile(result_path),
                                caption=f"✅ <b>Обработка завершена!</b>\n\n"
                                        f"🎨 Модель: {VIDEO_MODELS.get(model, model)}\n"
                                        f"💰 Потрачено: {cost} кредитов",
                                parse_mode="HTML"
                            )
                            output_file_id = sent_msg.video.file_id
                        
                        await update_job_status(session, job_id, "completed", output_file_id=output_file_id)
                    
                    # Cleanup
                    file_path.unlink(missing_ok=True)
                    result_path.unlink(missing_ok=True)
                    
                    logger.info(f"Job {job_id} completed successfully")
                    return
                
                elif topaz_job.status == "failed":
                    raise TopazAPIError(topaz_job.error or "Processing failed")
            
            # Timeout
            raise TopazAPIError("Processing timeout")
    
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        
        # Return credits
        async with get_session() as session:
            from src.services.jobs import get_job
            job = await get_job(session, job_id)
            
            await update_balance(session, job.telegram_id, cost)
            await update_job_status(session, job_id, "failed", error_message=str(e))
            
            await bot.send_message(
                job.telegram_id,
                f"❌ <b>Ошибка обработки!</b>\n\n"
                f"Причина: {str(e)}\n\n"
                f"💰 Кредиты возвращены: {cost}",
                parse_mode="HTML"
            )
        
        # Cleanup
        try:
            file_path.unlink(missing_ok=True)
        except:
            pass


@router.callback_query(F.data == "cancel", ProcessState.waiting_for_model)
async def cancel_processing(callback: CallbackQuery, state: FSMContext):
    """Cancel processing."""
    await callback.message.edit_text("❌ Обработка отменена")
    await state.clear()
    await callback.answer()


@router.message(Command("history"))
async def show_history(message: Message):
    """Show processing history."""
    async with get_session() as session:
        from src.services.jobs import get_user_jobs
        jobs = await get_user_jobs(session, message.from_user.id, limit=10)
    
    if not jobs:
        await message.answer("📜 История обработки пуста")
        return
    
    text = "📜 <b>История обработки:</b>\n\n"
    
    for job in jobs:
        status_emoji = {
            "completed": "✅",
            "failed": "❌",
            "processing": "⏳",
            "pending": "🕐",
        }.get(job.status, "❓")
        
        model_name = IMAGE_MODELS.get(job.model) or VIDEO_MODELS.get(job.model) or job.model
        
        text += (
            f"{status_emoji} {model_name}\n"
            f"   💰 {job.credits_cost} кредитов\n"
            f"   📅 {job.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )
    
    await message.answer(text, parse_mode="HTML")