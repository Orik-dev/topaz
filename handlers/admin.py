"""Admin handlers."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.db.engine import get_session
from src.services.users import get_all_active_users, ban_user, unban_user, update_balance
from src.services.broadcast import create_broadcast, execute_broadcast
from src.core.config import config
from src.core.logging import logger

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in config.ADMIN_IDS


class BroadcastState(StatesGroup):
    """Broadcast states."""
    waiting_for_message = State()
    confirm = State()


@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Show admin panel."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="💰 Управление балансом", callback_data="admin_balance"),
        ],
        [
            InlineKeyboardButton(text="📜 Логи", callback_data="admin_logs"),
        ],
    ])
    
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: CallbackQuery):
    """Show bot statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    async with get_session() as session:
        from sqlalchemy import select, func
        from src.db.models import User, Job, Payment
        
        # Total users
        result = await session.execute(select(func.count(User.telegram_id)))
        total_users = result.scalar()
        
        # Active users
        result = await session.execute(
            select(func.count(User.telegram_id)).where(User.is_active == True)
        )
        active_users = result.scalar()
        
        # Total jobs
        result = await session.execute(select(func.count(Job.id)))
        total_jobs = result.scalar()
        
        # Completed jobs
        result = await session.execute(
            select(func.count(Job.id)).where(Job.status == "completed")
        )
        completed_jobs = result.scalar()
        
        # Total revenue
        result = await session.execute(
            select(func.sum(Payment.amount_rub)).where(Payment.status == "completed")
        )
        total_revenue = result.scalar() or 0
        
        # Total credits sold
        result = await session.execute(
            select(func.sum(Payment.credits)).where(Payment.status == "completed")
        )
        total_credits_sold = result.scalar() or 0
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Активных: {active_users}\n"
        f"❌ Заблокированных: {total_users - active_users}\n\n"
        f"🎨 Всего обработок: {total_jobs}\n"
        f"✅ Успешных: {completed_jobs}\n"
        f"❌ Ошибок: {total_jobs - completed_jobs}\n\n"
        f"💰 Выручка: {total_revenue:,}₽\n"
        f"💳 Продано кредитов: {total_credits_sold:,}\n"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте сообщение для рассылки.\n"
        "Можно отправить текст, фото или видео с текстом.\n\n"
        "Отправьте /cancel для отмены.",
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.answer()


@router.message(BroadcastState.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext):
    """Receive broadcast message."""
    if message.text and message.text.startswith("/cancel"):
        await message.answer("❌ Рассылка отменена")
        await state.clear()
        return
    
    # Save message data
    data = {"text": message.text or message.caption or ""}
    
    if message.photo:
        data["media_type"] = "photo"
        data["media_file_id"] = message.photo[-1].file_id
    elif message.video:
        data["media_type"] = "video"
        data["media_file_id"] = message.video.file_id
    elif message.document:
        data["media_type"] = "document"
        data["media_file_id"] = message.document.file_id
    
    await state.update_data(**data)
    
    # Get user count
    async with get_session() as session:
        users = await get_all_active_users(session)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel"),
        ],
    ])
    
    await message.answer(
        f"📢 <b>Подтвердите рассылку</b>\n\n"
        f"👥 Получателей: {len(users)}\n\n"
        f"Отправить сообщение?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(BroadcastState.confirm)


@router.callback_query(F.data == "broadcast_confirm", BroadcastState.confirm)
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Confirm and execute broadcast."""
    data = await state.get_data()
    
    async with get_session() as session:
        broadcast = await create_broadcast(
            session,
            callback.from_user.id,
            data["text"],
            data.get("media_type"),
            data.get("media_file_id"),
        )
    
    await callback.message.edit_text(
        f"⏳ <b>Рассылка запущена</b>\n\n"
        f"ID: {broadcast.id}\n"
        f"Получателей: {broadcast.total}\n\n"
        f"Вы получите уведомление по завершении.",
        parse_mode="HTML"
    )
    
    # Execute broadcast in background
    from aiogram import Bot
    bot = callback.bot
    
    import asyncio
    asyncio.create_task(execute_broadcast_task(bot, session, broadcast.id, callback.from_user.id))
    
    await state.clear()
    await callback.answer()


async def execute_broadcast_task(bot, session, broadcast_id: str, admin_id: int):
    """Execute broadcast and notify admin."""
    from src.services.broadcast import execute_broadcast
    
    await execute_broadcast(session, bot, broadcast_id)
    
    # Notify admin
    async with get_session() as session:
        from src.db.models import BroadcastJob
        from sqlalchemy import select
        
        result = await session.execute(select(BroadcastJob).where(BroadcastJob.id == broadcast_id))
        broadcast = result.scalar_one()
        
        await bot.send_message(
            admin_id,
            f"✅ <b>Рассылка завершена</b>\n\n"
            f"ID: {broadcast.id}\n"
            f"📤 Отправлено: {broadcast.sent}\n"
            f"❌ Ошибок: {broadcast.failed}\n"
            f"⏸ Повторов: {broadcast.fallback}",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "broadcast_cancel", BroadcastState.confirm)
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Cancel broadcast."""
    await callback.message.edit_text("❌ Рассылка отменена")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin_users")
async def manage_users(callback: CallbackQuery):
    """Manage users."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "Отправьте команду:\n"
        "/ban USER_ID - забанить пользователя\n"
        "/unban USER_ID - разбанить пользователя\n\n"
        "Или вернитесь в меню:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
    )
    await callback.answer()


@router.message(Command("ban"))
async def ban_user_command(message: Message):
    """Ban user."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /ban USER_ID")
        return
    
    async with get_session() as session:
        await ban_user(session, user_id)
    
    await message.answer(f"✅ Пользователь {user_id} забанен")
    logger.info(f"Admin {message.from_user.id} banned user {user_id}")


@router.message(Command("unban"))
async def unban_user_command(message: Message):
    """Unban user."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        user_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /unban USER_ID")
        return
    
    async with get_session() as session:
        await unban_user(session, user_id)
    
    await message.answer(f"✅ Пользователь {user_id} разбанен")
    logger.info(f"Admin {message.from_user.id} unbanned user {user_id}")


@router.callback_query(F.data == "admin_balance")
async def manage_balance(callback: CallbackQuery):
    """Manage user balance."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 <b>Управление балансом</b>\n\n"
        "Отправьте команду:\n"
        "/addcredits USER_ID AMOUNT - добавить кредиты\n"
        "/removecredits USER_ID AMOUNT - убрать кредиты\n\n"
        "Или вернитесь в меню:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
        ])
    )
    await callback.answer()


@router.message(Command("addcredits"))
async def add_credits_command(message: Message):
    """Add credits to user."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /addcredits USER_ID AMOUNT")
        return
    
    async with get_session() as session:
        success = await update_balance(session, user_id, amount)
    
    if success:
        await message.answer(f"✅ Добавлено {amount} кредитов пользователю {user_id}")
        logger.info(f"Admin {message.from_user.id} added {amount} credits to user {user_id}")
    else:
        await message.answer(f"❌ Ошибка при добавлении кредитов")


@router.message(Command("removecredits"))
async def remove_credits_command(message: Message):
    """Remove credits from user."""
    if not is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /removecredits USER_ID AMOUNT")
        return
    
    async with get_session() as session:
        success = await update_balance(session, user_id, -amount)
    
    if success:
        await message.answer(f"✅ Удалено {amount} кредитов у пользователя {user_id}")
        logger.info(f"Admin {message.from_user.id} removed {amount} credits from user {user_id}")
    else:
        await message.answer(f"❌ Ошибка при удалении кредитов (недостаточно баланса?)")


@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    """Show recent logs."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    try:
        with open(config.LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            recent_logs = "".join(lines[-30:])  # Last 30 lines
        
        if len(recent_logs) > 4000:
            recent_logs = "..." + recent_logs[-4000:]
        
        await callback.message.edit_text(
            f"📜 <b>Последние логи:</b>\n\n"
            f"<code>{recent_logs}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_logs")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
            ])
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при чтении логов: {e}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")]
            ])
        )
    
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: CallbackQuery):
    """Return to admin panel."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"),
        ],
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="💰 Управление балансом", callback_data="admin_balance"),
        ],
        [
            InlineKeyboardButton(text="📜 Логи", callback_data="admin_logs"),
        ],
    ])
    
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()