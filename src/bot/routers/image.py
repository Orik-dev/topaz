from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User, TaskType
from src.bot.keyboards import image_models_keyboard, cancel_keyboard
from src.bot.states import ImageStates
from src.services.generation import GenerationService
from src.services.pricing import IMAGE_MODELS
from src.utils.file_validator import file_validator
from src.services.rate_limiter import rate_limiter
from src.services.telegram_safe import safe_send_text, safe_answer, safe_edit_text
from src.services.users import UserService
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📸 Улучшить фото")
async def image_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения фото"""
    await state.clear()
    
    text = (
        "📸 <b>Отправьте фото для улучшения</b>\n\n"
        "⚠️ <b>Ограничения:</b>\n"
        "• Максимум 20 МБ\n"
        "• Форматы: JPG, PNG, WEBP\n\n"
        "💡 Лучший результат с фото высокого качества"
    )
    
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(ImageStates.waiting_for_image)


@router.message(ImageStates.waiting_for_image, F.photo)
async def image_received(message: Message, state: FSMContext, user: User):
    """Фото получено - проверка и выбор модели"""
    photo = message.photo[-1]
    
    # Проверка rate limit (увеличено для тестирования)
    allowed, remaining = await rate_limiter.check_limit(
        user.telegram_id,
        "image_upload",
        30,  # ← УВЕЛИЧЕНО с 10 до 30
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
    valid, error_msg = file_validator.validate_image_size(photo.file_size)
    if not valid:
        await safe_send_text(
            bot=message.bot,
            chat_id=message.chat.id,
            text=f"❌ {error_msg}"
        )
        return
    
    await state.update_data(file_id=photo.file_id)
    
    text = (
        "✅ <b>Фото принято</b>\n\n"
        "Выберите модель обработки:"
    )
    
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=text,
        reply_markup=image_models_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(ImageStates.selecting_model)


@router.message(ImageStates.waiting_for_image)
async def wrong_content_type(message: Message):
    """Неправильный тип контента"""
    await safe_send_text(
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "❌ Пожалуйста, отправьте фото\n\n"
            "Поддерживаемые форматы: JPG, PNG, WEBP"
        )
    )


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
        await safe_answer(callback, "❌ Модель не найдена", show_alert=True)
        return
    
    model_info = IMAGE_MODELS[model_name]
    cost = model_info["cost"]
    
    # Проверка баланса
    if user.balance < cost:
        await safe_answer(
            callback,
            f"❌ Недостаточно генераций!\n\n"
            f"Требуется: {int(cost)}\n"
            f"У вас: {int(user.balance)}\n\n"
            f"Используйте /buy",
            show_alert=True
        )
        await state.clear()
        return
    
    data = await state.get_data()
    file_id = data.get("file_id")
    
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
    
    # 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: РЕЗЕРВИРУЕМ БАЛАНС СРАЗУ
    success = await UserService.deduct_credits(
        session=session,
        user=user,
        amount=cost,
        description=f"Резерв: обработка фото ({model_name})",
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
    
    text = (
        f"⏳ <b>Обработка началась...</b>\n\n"
        f"📊 Модель: {model_info['description']}\n"
        f"💰 Зарезервировано: {int(cost)} ген.\n\n"
        f"Обычно занимает 10-30 секунд"
    )
    
    await safe_edit_text(
        message=callback.message,
        text=text,
        parse_mode="HTML"
    )
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_image_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        image_file_id=file_id
    )
    
    await state.clear()
    await safe_answer(callback)
    
    logger.info(
        f"Image task created: task_id={task.id}, user={user.telegram_id}, "
        f"model={model_name}, balance_reserved=True"
    )