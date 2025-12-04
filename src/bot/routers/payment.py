from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User
from src.bot.keyboards import topup_keyboard, payment_method_keyboard, email_keyboard
from src.bot.states import PaymentStates
from src.services.payments import PaymentService, validate_email
from src.services.pricing import get_package_info
from src.services.telegram_safe import safe_send_text, safe_answer, safe_edit_text
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("buy"))
@router.message(F.text == "💳 Пополнить")
@router.callback_query(F.data == "buy")
async def cmd_buy(event: Message | CallbackQuery, user: User):
    """Пополнение баланса"""
    text = (
        f"⚡ <b>Ваш баланс: {int(user.balance)} ген.</b>\n\n"
        f"📊 Примерная стоимость:\n"
        f"• Фото: от 1 ген.\n"
        f"• Видео: от 3 ген./мин\n\n"
        f"💳 <b>Выберите пакет:</b>"
    )
    
    if isinstance(event, Message):
        await safe_send_text(
            bot=event.bot,
            chat_id=event.chat.id,
            text=text,
            reply_markup=topup_keyboard(),
            parse_mode="HTML"
        )
    else:
        await safe_edit_text(
            message=event.message,
            text=text,
            reply_markup=topup_keyboard(),
            parse_mode="HTML"
        )
        await safe_answer(event)


@router.callback_query(F.data.startswith("buy:"))
async def buy_package(callback: CallbackQuery):
    """Выбор пакета"""
    package_id = callback.data.split(":")[1]
    await callback.message.edit_text(
        "💳 <b>Выберите способ оплаты:</b>",
        reply_markup=payment_method_keyboard(package_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_yoo:"))
async def pay_yookassa_start(callback: CallbackQuery, state: FSMContext):
    """
    Начало оплаты YooKassa - запрос email
    """
    package_id = callback.data.split(":")[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price = package["price"]
    
    await state.update_data(package_id=package_id, rub=price, credits=total_gens)
    
    # ✅ Проверяем, сохранен ли email
    if callback.from_user.id:  # Здесь можно проверить в БД, есть ли email
        from sqlalchemy import select
        from src.db.engine import async_session_maker
        
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            user = result.scalar_one_or_none()
            
            if user and (user.email or getattr(user, 'receipt_opt_out', False)):
                # Email уже сохранен или отказался от чека
                try:
                    payment_data = await PaymentService.create_yookassa_payment(
                        session=session,
                        user=user,
                        amount=price,
                        credits=total_gens,
                        email=getattr(user, 'email', None)
                    )
                    await session.commit()
                    
                    await callback.message.edit_text(
                        f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
                        f"💰 Сумма: {price}₽\n\n"
                        f"Нажмите кнопку для оплаты:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="💳 Оплатить", url=payment_data["payment_url"])]
                        ]),
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    await state.clear()
                    return
                    
                except RuntimeError as e:
                    logger.error(f"YooKassa error: {e}")
                    await callback.message.edit_text(
                        "😔 <b>Временные технические работы</b>\n\n"
                        "Сервис оплаты картой временно недоступен.\n\n"
                        "🌟 Попробуйте оплату звёздами или попробуйте позже.",
                        reply_markup=payment_method_keyboard(package_id),
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    await state.clear()
                    return
                except Exception as e:
                    logger.exception(f"Unexpected payment error: {e}")
                    await callback.message.edit_text(
                        "⚠️ Ошибка создания платежа.\n\n"
                        "Попробуйте позже или выберите другой способ оплаты.",
                        reply_markup=payment_method_keyboard(package_id),
                        parse_mode="HTML"
                    )
                    await callback.answer()
                    await state.clear()
                    return
    
    # ✅ Email не сохранен - спрашиваем
    await callback.message.edit_text(
        f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
        f"💰 Сумма: {price}₽\n\n"
        f"📧 Нужен ли чек на email?",
        reply_markup=email_keyboard(package_id),
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.waiting_for_email)
    await callback.answer()


@router.callback_query(PaymentStates.waiting_for_email, F.data.startswith("no_receipt:"))
async def no_receipt(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Чек не нужен"""
    logger.info(f"📧 No receipt: user={callback.from_user.id}")
    
    data = await state.get_data()
    price = data.get("rub")
    total_gens = data.get("credits")
    
    # ✅ Сохраняем, что отказался от чека
    # Здесь можно добавить поле receipt_opt_out в модель User
    
    try:
        payment_data = await PaymentService.create_yookassa_payment(
            session=session,
            user=user,
            amount=price,
            credits=total_gens,
            email=None  # Используется TECH_EMAIL
        )
        await session.commit()
        
        await callback.message.edit_text(
            f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
            f"💰 Сумма: {price}₽\n\n"
            f"Нажмите кнопку для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_data["payment_url"])]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()
        await state.clear()
        
    except RuntimeError as e:
        logger.error(f"YooKassa error: {e}")
        package_id = data.get("package_id", "small")
        await callback.message.edit_text(
            "😔 <b>Временные технические работы</b>\n\n"
            "Сервис оплаты картой временно недоступен.\n\n"
            "Попробуйте позже или используйте оплату звёздами.",
            reply_markup=payment_method_keyboard(package_id),
            parse_mode="HTML"
        )
        await callback.answer()
        await state.clear()


@router.callback_query(PaymentStates.waiting_for_email, F.data.startswith("need_receipt:"))
async def need_receipt(callback: CallbackQuery, state: FSMContext):
    """Нужен чек - запрашиваем email"""
    logger.info(f"📧 Need receipt: user={callback.from_user.id}")
    
    await callback.message.edit_text(
        "📧 <b>Введите email для чека</b>\n\n"
        "Формат: example@domain.com\n\n"
        "💡 Email сохранится для будущих покупок",
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.entering_email)
    await callback.answer()


@router.message(PaymentStates.entering_email, F.text.startswith("/"))
async def handle_commands_in_email(message: Message, state: FSMContext):
    """Обработка команд при вводе email"""
    await state.clear()
    # Обрабатываем команду через глобальный роутер
    from src.bot.routers.commands import cmd_start, cmd_help, cmd_balance
    
    cmd = message.text.split()[0].lower()
    if cmd == "/start":
        await cmd_start(message, None)
    elif cmd == "/help":
        await cmd_help(message)
    elif cmd == "/balance":
        await cmd_balance(message, None)
    elif cmd == "/buy":
        await cmd_buy(message, None)


@router.message(PaymentStates.entering_email, F.text)
async def process_email(message: Message, session: AsyncSession, user: User, state: FSMContext):
    """Обработка введенного email"""
    email_input = message.text.strip()
    
    # Валидация
    validated_email = validate_email(email_input)
    
    if not validated_email:
        await message.answer(
            "❌ <b>Некорректный email</b>\n\n"
            "Проверьте:\n"
            "• Формат: example@domain.com\n"
            "• Нет пробелов\n"
            "• Домен с точкой (gmail.com)\n"
            "• Только латиница\n\n"
            "Введите снова:",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем email
    user.email = validated_email
    await session.flush()
    await session.commit()
    
    logger.info(f"✅ Email saved: user={message.from_user.id}, email={validated_email}")
    
    # Создаем платеж
    data = await state.get_data()
    price = data.get("rub")
    total_gens = data.get("credits")
    
    try:
        payment_data = await PaymentService.create_yookassa_payment(
            session=session,
            user=user,
            amount=price,
            credits=total_gens,
            email=validated_email
        )
        await session.commit()
        
        await message.answer(
            f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
            f"💰 Сумма: {price}₽\n"
            f"📧 Чек будет отправлен на: {validated_email}\n\n"
            f"Нажмите кнопку для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_data["payment_url"])]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        
    except RuntimeError as e:
        logger.error(f"YooKassa error: {e}")
        await message.answer(
            "😔 <b>Временные технические работы</b>\n\n"
            "Сервис оплаты временно недоступен.\n\n"
            "Попробуйте позже или используйте /buy для других способов оплаты.",
            parse_mode="HTML"
        )
        await state.clear()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Отменено")