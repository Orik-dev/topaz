"""Balance and payment handlers."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.engine import get_session
from src.services.users import get_balance, update_balance
from src.services.payments import create_payment, confirm_payment
from src.services.pricing import PACKS_RUB, PACKS_CREDITS
from src.core.config import config
from src.core.logging import logger

router = Router(name="balance")


@router.message(Command("balance"))
@router.callback_query(F.data == "balance")
async def show_balance(event):
    """Show user balance."""
    user_id = event.from_user.id
    message = event.message if hasattr(event, 'message') else event
    
    async with get_session() as session:
        balance = await get_balance(session, user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Пополнить", callback_data="topup")],
        [InlineKeyboardButton(text="📜 История платежей", callback_data="payment_history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="start")],
    ])
    
    text = (
        f"💰 <b>Ваш баланс:</b> {balance} кредитов\n\n"
        f"💡 Кредиты используются для обработки фото и видео.\n"
        f"Нажмите \"Пополнить\" чтобы купить кредиты."
    )
    
    if hasattr(event, 'message'):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await event.answer()
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(F.data == "topup")
async def show_topup_options(callback: CallbackQuery):
    """Show top-up packages."""
    keyboard_buttons = []
    
    for rub in PACKS_RUB:
        credits = PACKS_CREDITS[rub]
        price_per_credit = rub / credits
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{credits} кредитов - {rub}₽ (~{price_per_credit:.1f}₽/кредит)",
                callback_data=f"buy_{rub}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="balance")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    text = (
        "💳 <b>Выберите пакет:</b>\n\n"
        "💰 Чем больше пакет, тем выгоднее цена!\n\n"
        "✅ Оплата через Telegram Stars (безопасно и быстро)"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def process_payment(callback: CallbackQuery):
    """Process payment via Telegram Stars."""
    amount_rub = int(callback.data.split("_")[1])
    credits = PACKS_CREDITS[amount_rub]
    
    # Create payment record
    async with get_session() as session:
        payment = await create_payment(
            session,
            callback.from_user.id,
            amount_rub,
            provider="stars"
        )
    
    # Convert RUB to Stars (1 Star ≈ 2 RUB)
    stars_amount = amount_rub // 2
    
    # Create invoice
    prices = [LabeledPrice(label=f"{credits} кредитов", amount=stars_amount)]
    
    await callback.message.answer_invoice(
        title=f"Пополнение баланса",
        description=f"Покупка {credits} кредитов для обработки фото и видео",
        payload=payment.id,  # Payment ID as payload
        provider_token="",  # Empty for Stars
        currency="XTR",  # Telegram Stars
        prices=prices,
        max_tip_amount=0,
        suggested_tip_amounts=[],
    )
    
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Handle pre-checkout query."""
    # Always approve
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    """Handle successful payment."""
    payment_id = message.successful_payment.invoice_payload
    
    async with get_session() as session:
        # Confirm payment and credit balance
        success = await confirm_payment(
            session,
            payment_id,
            message.successful_payment.telegram_payment_charge_id
        )
        
        if success:
            balance = await get_balance(session, message.from_user.id)
            payment = await session.get(Payment, payment_id)
            
            await message.answer(
                f"✅ <b>Платёж успешно завершён!</b>\n\n"
                f"💰 Начислено: {payment.credits} кредитов\n"
                f"💳 Текущий баланс: {balance} кредитов\n\n"
                f"Спасибо за покупку! 🎉",
                parse_mode="HTML"
            )
            
            logger.info(f"Payment {payment_id} completed for user {message.from_user.id}")
        else:
            await message.answer(
                "❌ Ошибка при обработке платежа. Обратитесь в поддержку.",
                parse_mode="HTML"
            )
            logger.error(f"Failed to confirm payment {payment_id}")


@router.callback_query(F.data == "payment_history")
async def show_payment_history(callback: CallbackQuery):
    """Show payment history."""
    # TODO: Implement payment history
    await callback.answer("История платежей пока не доступна", show_alert=True)