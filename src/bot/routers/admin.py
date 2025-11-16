from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import User, Broadcast, Task
from src.bot.states import BroadcastStates
from src.services.users import UserService
from src.core.config import settings
import asyncio
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Рассылка (КАК В NANOBANANA!)"""
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
    """Обработка рассылки (ТОЧНО КАК В NANOBANANA - БЕЗ ВОРКЕРА!)"""
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
    
    # Рассылка (СИНХРОННО как в nanoBanan!)
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
            await asyncio.sleep(0.05)  # Rate limiting
            
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
    """Статистика"""
    if message.from_user.id not in settings.admin_list:
        return
    
    total_users = await UserService.get_user_count(session)
    
    result = await session.execute(select(Task))
    tasks = result.scalars().all()
    
    total_tasks = len(tasks)
    completed = len([t for t in tasks if t.status.value == "completed"])
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: {total_users}\n"
        f"📝 Задач: {total_tasks}\n"
        f"✅ Выполнено: {completed}",
        parse_mode="HTML"
    )