from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, TaskType
from src.bot.keyboards import image_models_keyboard, cancel_keyboard
from src.bot.states import ImageStates
from src.services.generation import GenerationService
from src.services.pricing import IMAGE_MODELS
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📸 Улучшить фото")
async def image_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения фото"""
    await message.answer(
        "📸 Отправьте фото для улучшения",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(ImageStates.waiting_for_image)


@router.message(ImageStates.waiting_for_image, F.photo)
async def image_received(message: Message, state: FSMContext):
    """Фото получено - выбор модели"""
    photo = message.photo[-1]
    await state.update_data(file_id=photo.file_id)
    
    await message.answer(
        "🎨 Выберите модель обработки:",
        reply_markup=image_models_keyboard()
    )
    await state.set_state(ImageStates.selecting_model)


@router.callback_query(ImageStates.selecting_model, F.data.startswith("img_model:"))
async def process_image_model(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User
):
    """Обработка фото с выбранной моделью"""
    model_name = callback.data.split(":")[1]
    
    if model_name not in IMAGE_MODELS:
        await callback.answer("❌ Модель не найдена", show_alert=True)
        return
    
    model_info = IMAGE_MODELS[model_name]
    cost = model_info["cost"]
    
    if user.balance < cost:
        await callback.answer(
            f"❌ Недостаточно генераций! Требуется: {cost}",
            show_alert=True
        )
        await state.clear()
        return
    
    await callback.message.edit_text("⏳ Обработка началась...")
    
    data = await state.get_data()
    file_id = data.get("file_id")
    
    # Скачиваем фото
    file = await callback.bot.get_file(file_id)
    image_data = await callback.bot.download_file(file.file_path)
    
    # Создаем задачу
    task = await GenerationService.create_task(
        session=session,
        user=user,
        task_type=TaskType.IMAGE_ENHANCE,
        model=model_name,
        cost=cost,
        input_file_id=file_id,
        parameters={
            "endpoint": model_info["endpoint"],
            "face_enhancement": True,
            "face_enhancement_strength": 0.8
        }
    )
    await session.commit()
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_image_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        image_data=image_data.read()
    )
    
    await state.clear()
    await callback.answer()