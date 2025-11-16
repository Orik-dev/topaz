from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, TaskType
from src.bot.keyboards import video_models_keyboard, cancel_keyboard
from src.bot.states import VideoStates
from src.services.generation import GenerationService
from src.services.pricing import VIDEO_MODELS
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "🎬 Улучшить видео")
async def video_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения видео"""
    await state.clear()  # ✅ Очищаем состояние
    await message.answer(
        "🎬 Отправьте видео для улучшения\n\n"
        "⚠️ Максимум 50 МБ, до 5 минут",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(VideoStates.waiting_for_video)


@router.message(VideoStates.waiting_for_video, F.video)
async def video_received(message: Message, state: FSMContext):
    """Видео получено - выбор модели"""
    video = message.video
    
    # Проверяем размер
    if video.file_size > 50 * 1024 * 1024:  # 50 МБ
        await message.answer("❌ Файл слишком большой. Максимум 50 МБ")
        return
    
    # Проверяем длительность
    if video.duration > 300:  # 5 минут
        await message.answer("❌ Видео слишком длинное. Максимум 5 минут")
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
        f"🎬 Длительность: {duration_minutes:.1f} мин\n\n"
        f"Выберите модель обработки:",
        reply_markup=video_models_keyboard()
    )
    await state.set_state(VideoStates.selecting_model)


@router.message(VideoStates.waiting_for_video)
async def wrong_content_type(message: Message):
    """Неправильный тип контента"""
    await message.answer("❌ Пожалуйста, отправьте видео")


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
        f"⏳ Обработка началась...\n\n"
        f"Это займет несколько минут.\n"
        f"Мы пришлем результат когда всё будет готово."
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
                "container": "mp4"
            },
            "output": {
                "width": data.get("width", 1280) * 2,
                "height": data.get("height", 720) * 2,
                "frameRate": model_info.get("output_fps", 30),
                "container": "mp4",
                "audioCodec": "AAC",
                "audioTransfer": "Copy"
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