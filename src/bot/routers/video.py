from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, TaskType
from src.bot.keyboards import video_models_keyboard, cancel_keyboard
from src.bot.states import VideoStates
from src.services.generation import GenerationService
from src.services.pricing import VIDEO_MODELS
from src.utils.file_validator import file_validator
from src.services.rate_limiter import rate_limiter
from src.core.config import settings
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "🎬 Улучшить видео")
async def video_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения видео"""
    await state.clear()
    await message.answer(
        "🎬 <b>Отправьте видео для улучшения</b>\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Максимум 100 МБ\n"
        "• До 5 минут длительности\n"
        "• Форматы: MP4, MOV\n\n"
        "💡 Для больших видео используйте компрессию",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(VideoStates.waiting_for_video)


@router.message(VideoStates.waiting_for_video, F.video)
async def video_received(message: Message, state: FSMContext, user: User):
    """Видео получено - проверка и выбор модели"""
    video = message.video
    
    # Проверка rate limit
    allowed, remaining = await rate_limiter.check_limit(
        user.telegram_id,
        "video_upload",
        3,  # 3 видео
        3600  # в час
    )
    
    if not allowed:
        await message.answer(
            f"⏱ <b>Слишком много запросов</b>\n\n"
            f"Подождите {remaining // 60} минут перед следующей загрузкой",
            parse_mode="HTML"
        )
        return
    
    # Валидация размера
    valid, error_msg = file_validator.validate_video_size(video.file_size)
    if not valid:
        await message.answer(f"❌ {error_msg}")
        return
    
    # Валидация длительности
    valid, error_msg = file_validator.validate_video_duration(video.duration)
    if not valid:
        await message.answer(f"❌ {error_msg}")
        return
    
    duration_minutes = max(1.0, video.duration / 60.0)
    
    await state.update_data(
        file_id=video.file_id,
        duration=video.duration,
        duration_minutes=duration_minutes,
        width=video.width,
        height=video.height,
        file_size=video.file_size
    )
    
    await message.answer(
        f"✅ <b>Видео принято</b>\n\n"
        f"📊 Длительность: {duration_minutes:.1f} мин\n"
        f"📐 Разрешение: {video.width}x{video.height}\n"
        f"💾 Размер: {video.file_size // 1024 // 1024} МБ\n\n"
        f"Выберите модель обработки:",
        reply_markup=video_models_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(VideoStates.selecting_model)


@router.message(VideoStates.waiting_for_video)
async def wrong_content_type(message: Message):
    """Неправильный тип контента"""
    await message.answer(
        "❌ Пожалуйста, отправьте видео\n\n"
        "Поддерживаемые форматы: MP4, MOV"
    )


@router.callback_query(VideoStates.selecting_model, F.data.startswith("vid_model:"))
async def process_video_model(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User
):
    """Обработка видео с выбранной моделью"""
    model_key = callback.data.split(":")[1]
    
    if model_key not in VIDEO_MODELS:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    model_info = VIDEO_MODELS[model_key]
    data = await state.get_data()
    duration_minutes = data.get("duration_minutes", 1.0)
    
    cost = int(model_info["cost_per_minute"] * duration_minutes)
    
    if user.balance < cost:
        await callback.answer(
            f"❌ Недостаточно генераций!\n\n"
            f"Требуется: {cost} ген.\n"
            f"У вас: {int(user.balance)} ген.\n\n"
            f"Используйте /buy",
            show_alert=True
        )
        await state.clear()
        return
    
    await callback.message.edit_text(
        f"🎬 <b>Обработка началась!</b>\n\n"
        f"⏳ Это займет несколько минут.\n"
        f"📊 Модель: {model_info['description']}\n"
        f"💰 Стоимость: {cost} ген.\n\n"
        f"Мы пришлем результат когда всё будет готово.\n"
        f"Вы можете отменить обработку в любой момент.",
        parse_mode="HTML"
    )
    
    file_id = data.get("file_id")
    
    # Создаем задачу
    task = await GenerationService.create_task(
        session=session,
        user=user,
        task_type=TaskType.VIDEO_ENHANCE,
        model=model_key,
        cost=cost,
        input_file_id=file_id,
        parameters={
            "source": {
                "width": data.get("width", 1280),
                "height": data.get("height", 720),
                "duration": data.get("duration", 60),
                "frameRate": 30,
                "container": "mp4",
                "frameCount": int(data.get("duration", 60) * 30)
            },
            "output": {
                "width": data.get("width", 1280) * 2,
                "height": data.get("height", 720) * 2,
                "frameRate": model_info.get("output_fps", 30),
                "container": "mp4",
                "audioCodec": "AAC",
                "audioTransfer": "Copy",
                "videoEncoder": "H264",
                "dynamicCompressionLevel": "Mid"
            },
            "filters": model_info["filters"]
        }
    )
    await session.commit()
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_video_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        video_file_id=file_id
    )
    
    await state.clear()
    await callback.answer()
    
    logger.info(f"Video task created: task_id={task.id}, user={user.telegram_id}, model={model_key}, cost={cost}")


@router.callback_query(F.data.startswith("cancel_task:"))
async def cancel_task_callback(callback: CallbackQuery):
    """Отмена обработки"""
    try:
        task_id = int(callback.data.split(":")[1])
        
        # Устанавливаем флаг отмены
        redis = await aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_CACHE
        )
        await redis.setex(f"cancel_task:{task_id}", 3600, "1")
        await redis.aclose()
        
        await callback.message.edit_text(
            "⏹ <b>Отмена обработки...</b>\n\n"
            "Генерации будут возвращены автоматически.",
            parse_mode="HTML"
        )
        await callback.answer("Обработка отменяется...")
        
        logger.info(f"User requested cancel: task={task_id}")
        
    except Exception as e:
        logger.error(f"Cancel callback error: {e}")
        await callback.answer("Ошибка отмены", show_alert=True)