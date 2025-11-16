from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import User, Broadcast, Task
from src.bot.keyboards import main_keyboard, topup_keyboard, payment_method_keyboard, cancel_keyboard
from src.bot.states import BroadcastStates, ImageStates, VideoStates
from src.services.users import UserService
from src.services.payments import PaymentService
from src.services.pricing import get_package_info, get_task_cost, calculate_stars_amount
from src.services.generation import GenerationService
from src.db.models import TaskType
from src.core.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)
router = Router()


# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@router.message(CommandStart())
async def cmd_start(message: Message, user: User):
    """Команда /start"""
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"🤖 Я бот для улучшения фото и видео с помощью AI\n\n"
        f"⚡ Ваш баланс: {int(user.balance)} ген.\n\n"
        f"Выберите действие:",
        reply_markup=main_keyboard()
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """Команда /help"""
    await message.answer(
        f"📖 <b>Справка</b>\n\n"
        f"<b>Как использовать:</b>\n"
        f"📸 Улучшить фото - отправьте фото (1 ген.)\n"
        f"🎬 Улучшить видео - отправьте видео (5 ген./мин)\n\n"
        f"<b>Пополнение:</b>\n"
        f"💳 Карта/СБП через YooKassa\n"
        f"⭐ Telegram Stars\n\n"
        f"<b>Возврат генераций:</b>\n"
        f"При ошибке обработки генерации возвращаются автоматически\n\n"
        f"💬 Поддержка: @{settings.SUPPORT_USERNAME}",
        parse_mode="HTML"
    )


@router.message(Command("bots"))
async def cmd_bots(message: Message):
    """Команда /bots - наши боты"""
    await message.answer(
        f"🤖 <b>Наши боты:</b>\n\n"
        f"📸 @{message.bot.me.username} - Улучшение фото/видео AI\n\n"
        f"💬 Поддержка: @{settings.SUPPORT_USERNAME}",
        parse_mode="HTML"
    )


@router.message(Command("balance"))
@router.message(F.text == "💰 Баланс")
async def cmd_balance(message: Message, user: User):
    """Баланс"""
    await message.answer(
        f"⚡ <b>Ваш баланс: {int(user.balance)} ген.</b>\n\n"
        f"📊 Стоимость:\n"
        f"• Фото: 1 ген.\n"
        f"• Видео: 5 ген./мин",
        parse_mode="HTML"
    )


@router.message(Command("topup"))
@router.message(F.text == "💳 Пополнить")
@router.callback_query(F.data == "topup")
async def cmd_topup(event: Message | CallbackQuery):
    """Пополнение"""
    text = "💳 <b>Пополнение баланса</b>\n\nВыберите пакет генераций:"
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=topup_keyboard(), parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=topup_keyboard(), parse_mode="HTML")
        await event.answer()


# ========== ОБРАБОТКА ФОТО ==========

@router.message(F.text == "📸 Улучшить фото")
async def image_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения фото"""
    await message.answer(
        "📸 Отправьте фото для улучшения\n\n"
        "💰 Стоимость: 1 генерация",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(ImageStates.waiting_for_image)


@router.message(ImageStates.waiting_for_image, F.photo)
async def process_image(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User
):
    """Обработка фото"""
    cost = get_task_cost("image_enhance")
    
    if user.balance < cost:
        await message.answer(
            f"❌ Недостаточно генераций!\n\n"
            f"Требуется: {cost} ген.\n"
            f"У вас: {int(user.balance)} ген.",
            reply_markup=topup_keyboard()
        )
        await state.clear()
        return
    
    await message.answer("⏳ Обработка началась...")
    
    # Скачиваем фото
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    image_data = await message.bot.download_file(file.file_path)
    
    # Создаем задачу
    task = await GenerationService.create_task(
        session=session,
        user=user,
        task_type=TaskType.IMAGE_ENHANCE,
        model="Standard V2",
        cost=cost,
        input_file_id=photo.file_id,
        parameters={"face_enhancement": True, "face_enhancement_strength": 0.8}
    )
    await session.commit()
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_image_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        image_data=image_data.read()
    )
    
    await state.clear()


# ========== ОБРАБОТКА ВИДЕО ==========

@router.message(F.text == "🎬 Улучшить видео")
async def video_enhance_start(message: Message, state: FSMContext):
    """Начало улучшения видео"""
    await message.answer(
        "🎬 Отправьте видео для улучшения\n\n"
        "💰 Стоимость: 5 генераций за минуту",
        reply_markup=cancel_keyboard()
    )
    await state.set_state(VideoStates.waiting_for_video)


@router.message(VideoStates.waiting_for_video, F.video)
async def process_video(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User
):
    """Обработка видео"""
    video = message.video
    duration_minutes = max(1.0, video.duration / 60.0)
    cost = get_task_cost("video_enhance", duration_minutes)
    
    if user.balance < cost:
        await message.answer(
            f"❌ Недостаточно генераций!\n\n"
            f"Требуется: {cost} ген.\n"
            f"У вас: {int(user.balance)} ген.",
            reply_markup=topup_keyboard()
        )
        await state.clear()
        return
    
    await message.answer("⏳ Задача поставлена в очередь...")
    
    # Создаем задачу
    video_params = {
        "source": {
            "resolution": {"width": video.width, "height": video.height},
            "container": "mp4",
            "size": video.file_size,
            "duration": int(duration_minutes * 60 * 1000),
            "frameRate": 30,
            "frameCount": int(duration_minutes * 60 * 30)
        },
        "output": {
            "resolution": {"width": video.width * 2, "height": video.height * 2},
            "audioCodec": "AAC",
            "audioTransfer": "Copy",
            "frameRate": 30,
            "dynamicCompressionLevel": "High",
            "container": "mp4"
        },
        "filters": [{
            "model": "prob-4",
            "videoType": "Progressive",
            "auto": "Relative"
        }]
    }
    
    task = await GenerationService.create_task(
        session=session,
        user=user,
        task_type=TaskType.VIDEO_ENHANCE,
        model="Proteus prob-4",
        cost=cost,
        input_file_id=video.file_id,
        parameters=video_params
    )
    await session.commit()
    
    # Ставим в очередь ARQ
    await GenerationService.enqueue_video_task(
        task_id=task.id,
        user_telegram_id=user.telegram_id,
        video_file_id=video.file_id
    )
    
    await state.clear()


# ========== ПЛАТЕЖИ ==========

@router.callback_query(F.data.startswith("buy:"))
async def buy_package(callback: CallbackQuery):
    """Выбор пакета"""
    package_id = callback.data.split(":")[1]
    await callback.message.edit_text(
        "💳 Выберите способ оплаты:",
        reply_markup=payment_method_keyboard(package_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_yoo:"))
async def pay_yookassa(callback: CallbackQuery, session: AsyncSession, user: User):
    """Оплата через YooKassa"""
    package_id = callback.data.split(":")[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price = package["price"]
    
    try:
        payment_data = await PaymentService.create_yookassa_payment(
            session=session,
            user=user,
            amount=price,
            credits=total_gens
        )
        
        await callback.message.edit_text(
            f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
            f"Сумма: {price}₽\n\n"
            f"Нажмите кнопку ниже для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_data["payment_url"])]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Payment creation error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания платежа", show_alert=True)


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Отменено")


# ========== АДМИН КОМАНДЫ ==========

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Рассылка (только админы)"""
    if message.from_user.id not in settings.admin_list:
        return
    
    await message.answer(
        "📢 <b>Рассылка</b>\n\n"
        "Отправьте сообщение для рассылки\n"
        "(текст, фото или видео с подписью)",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastStates.waiting_for_content)


@router.message(BroadcastStates.waiting_for_content)
async def process_broadcast(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка рассылки"""
    if message.from_user.id not in settings.admin_list:
        return
    
    # Получаем всех пользователей
    result = await session.execute(select(User))
    users = result.scalars().all()
    
    # Определяем тип контента
    text = message.text or message.caption or ""
    photo_id = None
    video_id = None
    
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.video:
        video_id = message.video.file_id
    
    # Создаем запись рассылки
    broadcast = Broadcast(
        message_text=text,
        total_users=len(users),
        created_by=message.from_user.id,
        status="in_progress"
    )
    session.add(broadcast)
    await session.commit()
    
    # Рассылка
    sent = 0
    failed = 0
    
    for user in users:
        try:
            if photo_id:
                await message.bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=photo_id,
                    caption=text
                )
            elif video_id:
                await message.bot.send_video(
                    chat_id=user.telegram_id,
                    video=video_id,
                    caption=text
                )
            else:
                await message.bot.send_message(
                    chat_id=user.telegram_id,
                    text=text
                )
            
            sent += 1
            await asyncio.sleep(0.05)
            
        except Exception as e:
            logger.error(f"Broadcast error for user {user.telegram_id}: {e}")
            failed += 1
    
    # Обновляем запись
    broadcast.sent_count = sent
    broadcast.failed_count = failed
    broadcast.status = "completed"
    await session.commit()
    
    await message.answer(
        f"✅ Рассылка завершена\n\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}"
    )
    await state.clear()


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    """Статистика (только админы)"""
    if message.from_user.id not in settings.admin_list:
        return
    
    total_users = await UserService.get_user_count(session)
    
    result = await session.execute(select(Task))
    tasks = result.scalars().all()
    
    total_tasks = len(tasks)
    completed = len([t for t in tasks if t.status == "completed"])
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📝 Задач: {total_tasks}\n"
        f"✅ Выполнено: {completed}",
        parse_mode="HTML"
    )


# Импорты для InlineKeyboardMarkup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton