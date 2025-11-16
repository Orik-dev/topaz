from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User
from src.bot.keyboards import topup_keyboard, payment_method_keyboard, email_keyboard
from src.bot.states import PaymentStates
from src.services.users import UserService
from src.services.payments import PaymentService
from src.services.pricing import get_package_info, calculate_stars_amount
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import re

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("buy"))
@router.message(F.text == "💳 Купить")
@router.callback_query(F.data == "buy")
async def cmd_buy(event: Message | CallbackQuery, user: User):
    """Команда /buy - БАЛАНС + ПОКУПКА"""
    text = (
        f"⚡ <b>Ваш баланс: {int(user.balance)} ген.</b>\n\n"
        f"📊 Примерная стоимость:\n"
        f"• Фото: от 1 ген.\n"
        f"• Видео: от 3 ген./мин\n\n"
        f"💳 <b>Выберите пакет генераций:</b>"
    )
    
    if isinstance(event, Message):
        await event.answer(text, reply_markup=topup_keyboard(), parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=topup_keyboard(), parse_mode="HTML")
        await event.answer()


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
async def pay_yookassa_email(callback: CallbackQuery, state: FSMContext):
    """Оплата YooKassa - запрос email"""
    package_id = callback.data.split(":")[1]
    
    await state.update_data(package_id=package_id)
    
    await callback.message.edit_text(
        "✉️ <b>Получение чека</b>\n\n"
        "Отправьте ваш email для получения чека\n"
        "или нажмите кнопку ниже:",
        reply_markup=email_keyboard(package_id),
        parse_mode="HTML"
    )
    await state.set_state(PaymentStates.waiting_for_email)
    await callback.answer()


@router.message(PaymentStates.waiting_for_email, F.text)
async def process_email(message: Message, session: AsyncSession, user: User, state: FSMContext):
    """Обработка введенного email"""
    email = message.text.strip()
    
    # Валидация email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        await message.answer("❌ Неверный формат email. Попробуйте еще раз или нажмите 'Чек не нужен'")
        return
    
    data = await state.get_data()
    package_id = data.get("package_id")
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price = package["price"]
    
    try:
        payment_data = await PaymentService.create_yookassa_payment(
            session=session,
            user=user,
            amount=price,
            credits=total_gens,
            email=email
        )
        
        await message.answer(
            f"💳 <b>Оплата {total_gens} генераций</b>\n\n"
            f"Сумма: {price}₽\n"
            f"Чек будет отправлен на: {email}\n\n"
            f"Нажмите кнопку ниже для оплаты:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_data["payment_url"])]
            ]),
            parse_mode="HTML"
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Payment creation error: {e}", exc_info=True)
        await message.answer("❌ Ошибка создания платежа. Попробуйте позже.")
        await state.clear()


@router.callback_query(F.data.startswith("no_receipt:"))
async def no_receipt(callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext):
    """Чек не нужен - используем дефолтный email для ИП"""
    package_id = callback.data.split(":")[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price = package["price"]
    
    try:
        payment_data = await PaymentService.create_yookassa_payment(
            session=session,
            user=user,
            amount=price,
            credits=total_gens,
            email=None
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
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Payment creation error: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания платежа", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery, session: AsyncSession, user: User):
    """Оплата через Stars"""
    package_id = callback.data.split(":")[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price_rub = package["price"]
    stars_amount = calculate_stars_amount(price_rub)
    
    await callback.message.answer_invoice(
        title=f"{total_gens} генераций",
        description=f"Пополнение баланса на {total_gens} генераций",
        payload=f"stars_{package_id}_{user.id}",
        currency="XTR",
        prices=[{"label": f"{total_gens} генераций", "amount": stars_amount}]
    )
    
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await state.clear()
    await callback.message.delete()
    await callback.answer("❌ Отменено")