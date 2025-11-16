from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import User
from src.services.users import UserService
from src.services.pricing import get_package_info, calculate_stars_amount
from src.bot.keyboards import topup_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()


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


@router.message(F.successful_payment)
async def successful_payment_stars(message: Message, session: AsyncSession, user: User):
    """Успешная оплата Stars"""
    payload = message.successful_payment.invoice_payload
    
    if not payload.startswith("stars_"):
        return
    
    parts = payload.split("_")
    package_id = parts[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    
    # Добавляем генерации
    await UserService.add_credits(
        session=session,
        user=user,
        amount=total_gens,
        description=f"Пополнение через Stars",
        reference_type="payment_stars"
    )
    await session.commit()
    
    await message.answer(
        f"✅ Оплата успешна!\n\n"
        f"💰 Начислено: {total_gens} ген.\n"
        f"⚡ Баланс: {int(user.balance)} gen.")