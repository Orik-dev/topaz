from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
from src.services.telegram_safe import safe_send_text, safe_answer, safe_edit_text
from src.services.users import UserService
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "🎬 Улучшить видео")
async def video_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения видео"""
    await state.clear()
    
    text = (
        "🎬 <b>Отправьте видео для улучшения</b>\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Максимум 2 ГБ\n"
        "• До 10 минут длительности\n"
        "• Форматы: MP4, MOV\n\n"
        "💡 Большие видео обрабатываются дольше (5-15 мин)"
    )
    
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(VideoStates.waiting_for_video)


@router.message(VideoStates.waiting_for_video, F.video)
async def video_received(message: Message, state: FSMContext, user: User):
    """Видео получено - проверка и выбор модели"""
    video = message.video
    
    # Проверка rate limit (увеличено для тестирования)
    allowed, remaining = await rate_limiter.check_limit(
        user.telegram_id,
        "video_upload",
        20,  # ← УВЕЛИЧЕНО с 3 до 20
        3600  # в час
    )
    
    if not allowed:
        text = (
            f"⏱ <b>Слишком много запросов</b>\n\n"
            f"Подождите {remaining // 60} минут перед следующей загрузкой"
        )
        await safe_send_text(
            bot=message.bot,
            chat_id=message.chat.id,
            text=text,
            parse_mode="HTML"
        )
        return
    
    # Валидация размера
    valid, error_msg = file_validator.validate_video_size(video.file_size)
    if not valid:
        await safe_send_text(
            bot=message.bot,
            chat_id=message.chat.id,
            text=f"❌ {error_msg}"
        )
        return
    
    # Валидация длительности
    valid, error_msg = file_validator.validate_video_duration(video.duration)
    if not valid:
        await safe_send_text(
            bot=message.bot,
            chat_id=message.chat.id,
            text=f"❌ {error_msg}"
        )
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
    
    text = (
        f"✅ <b>Видео принято</b>\n\n"
        f"📊 Длительность: {duration_minutes:.1f} мин\n"
        f"📐 Разрешение: {video.width}x{video.height}\n"
        f"💾 Размер: {video.file_size // 1024 // 1024} МБ\n\n"
        f"Выберите модель обработки:"
    )
    
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=video_models_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(VideoStates.selecting_model)


@router.message(VideoStates.waiting_for_video)
async def wrong_content_type(message: Message):
    """Неправильный тип контента"""
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "❌ Пожалуйста, отправьте видео\n\n"
            "Поддерживаемые форматы: MP4, MOV"
        )
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
        await safe_answer(callback, "❌ Модель не найдена", show_alert=True)
        return
    
    model_info = VIDEO_MODELS[model_key]
    data = await state.get_data()
    duration_minutes = data.get("duration_minutes", 1.0)
    duration_seconds = data.get("duration", 60)
    
    cost = int(model_info["cost_per_minute"] * duration_minutes)
    
    # Проверка баланса
    if user.balance < cost:
        await safe_answer(
            callback,
            f"❌ Недостаточно генераций!\n\n"
            f"Требуется: {cost} ген.\n"
            f"У вас: {int(user.balance)} ген.\n\n"
            f"Используйте /buy",
            show_alert=True
        )
        await state.clear()
        return
    
    # Структура параметров
    width = data.get("width", 1280)
    height = data.get("height", 720)
    frame_count = int(duration_seconds * 30)
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
                "container": "mp4",
                "duration": int(duration_seconds),
                "frameRate": 30,
                "frameCount": frame_count,
                "resolution": {
                    "width": width,
                    "height": height
                }
            },
            "output": {
                "frameRate": model_info.get("output_fps", 30),
                "audioTransfer": "Copy",
                "audioCodec": "AAC",
                "videoEncoder": "H265",  # ← ИСПРАВЛЕНО с H264
                "videoProfile": "Main",
                "dynamicCompressionLevel": "Mid",
                "resolution": {
                    "width": width * 2,
                    "height": height * 2
                }
            },
            "filters": model_info["filters"]
        }
    )
    
    # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: РЕЗЕРВИРУЕМ БАЛАНС СРАЗУ
    success = await UserService.deduct_credits(
        session=session,
        user=user,
        amount=cost,
        description=f"Резерв: обработка видео ({model_key})",
        reference_type="task_reserve",
        reference_id=task.id
    )
    
    if not success:
        await safe_answer(
            callback,
            "❌ Недостаточно генераций!",
            show_alert=True
        )
        await session.delete(task)
        await session.commit()
        await state.clear()
        return
    
    await session.commit()
    
    # Клавиатура с отменой
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_task:{task.id}")]
    ])
    
    # Сообщение пользователю
    text = (
        f"🎬 <b>Обработка началась!</b>\n\n"
        f"⏳ Это займет несколько минут.\n"
        f"📊 Модель: {model_info['description']}\n"
        f"💰 Зарезервировано: {cost} ген.\n\n"
        f"Мы пришлем результат когда всё будет готово.\n"
        f"Вы можете отменить обработку в любой момент."
    )
    
    await safe_edit_text(
        message=callback.message,
        text=text,
        reply_markup=cancel_kb,
        parse_mode="HTML"
    )
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_video_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        video_file_id=file_id
    )
    
    await state.clear()
    await safe_answer(callback)
    
    logger.info(
        f"Video task created: task_id={task.id}, user={user.telegram_id}, "
        f"model={model_key}, cost={cost}, balance_reserved=True"
    )


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
        await redis.close()  # ← ИСПРАВЛЕНО с aclose()
        
        text = (
            "⏹ <b>Отмена обработки...</b>\n\n"
            "Генерации будут возвращены автоматически."
        )
        
        await safe_edit_text(
            message=callback.message,
            text=text,
            parse_mode="HTML"
        )
        await safe_answer(callback, "Обработка отменяется...")
        
        logger.info(f"User requested cancel: task={task_id}")
        
    except Exception as e:
        logger.error(f"Cancel callback error: {e}")
        await safe_answer(callback, "Ошибка отмены", show_alert=True)