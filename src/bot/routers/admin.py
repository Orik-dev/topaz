from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import User, Broadcast
from src.bot.states import BroadcastStates
from src.core.config import settings
from src.db.engine import async_session_maker
from src.services.telegram_safe import safe_send_text, safe_send_photo, safe_send_video  # ✅ ДОБАВЛЕНО
import asyncio
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Рассылка (ТОЛЬКО ДЛЯ АДМИНОВ)"""
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
async def process_broadcast(message: Message, state: FSMContext):
    """Обработка рассылки с telegram_safe защитой"""
    if message.from_user.id not in settings.admin_list:
        return
    
    async with async_session_maker() as session:
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
        
        # Рассылка с SAFE защитой
        sent_count = 0
        failed_count = 0
        
        status_message = await message.answer(
            f"📊 Рассылка началась...\n"
            f"Всего пользователей: {len(users)}"
        )
        
        for i, user in enumerate(users):
            success = False
            
            # ✅ ИСПОЛЬЗУЕМ SAFE ФУНКЦИИ
            if photo_id:
                msg = await safe_send_photo(
                    bot=message.bot,
                    chat_id=user.telegram_id,
                    photo=photo_id,
                    caption=text,
                    parse_mode="HTML"
                )
                success = msg is not None
            elif video_id:
                msg = await safe_send_video(
                    bot=message.bot,
                    chat_id=user.telegram_id,
                    video=video_id,
                    caption=text,
                    parse_mode="HTML"
                )
                success = msg is not None
            else:
                msg = await safe_send_text(
                    bot=message.bot,
                    chat_id=user.telegram_id,
                    text=text,
                    parse_mode="HTML"
                )
                success = msg is not None
            
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
            # Обновляем статус каждые 10 пользователей
            if (i + 1) % 10 == 0:
                await status_message.edit_text(
                    f"📊 Рассылка...\n"
                    f"Отправлено: {sent_count}/{len(users)}\n"
                    f"Ошибок: {failed_count}"
                )
            
            # Задержка
            await asyncio.sleep(0.05)
        
        # Обновляем запись в БД
        broadcast.sent_count = sent_count
        broadcast.failed_count = failed_count
        broadcast.status = "completed"
        await session.commit()
        
        await status_message.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📊 Всего: {len(users)}\n"
            f"✅ Отправлено: {sent_count}\n"
            f"❌ Ошибок: {failed_count}",
            parse_mode="HTML"
        )
        
        await state.clear()


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика"""
    if message.from_user.id not in settings.admin_list:
        return
    
    async with async_session_maker() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        active_users = [u for u in users if u.balance > 0]
        total_balance = sum(u.balance for u in users)
        
        await message.answer(
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"⚡ Активных: {len(active_users)}\n"
            f"💰 Общий баланс: {int(total_balance)} ген.",
            parse_mode="HTML"
        )