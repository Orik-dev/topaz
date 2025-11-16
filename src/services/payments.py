"""Payment service for handling YooKassa payments."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Payment
from src.services.pricing import credits_for_rub


async def create_payment(
    session: AsyncSession,
    telegram_id: int,
    amount_rub: int,
    provider: str = "yookassa",
) -> Payment:
    """Создать новый платёж."""
    credits = credits_for_rub(amount_rub)
    
    payment = Payment(
        id=str(uuid.uuid4()),
        telegram_id=telegram_id,
        amount_rub=amount_rub,
        credits=credits,
        provider=provider,
        status="pending",
        created_at=datetime.utcnow(),
    )
    
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    
    return payment


async def get_payment(session: AsyncSession, payment_id: str) -> Optional[Payment]:
    """Получить платёж по ID."""
    result = await session.execute(select(Payment).where(Payment.id == payment_id))
    return result.scalar_one_or_none()


async def confirm_payment(session: AsyncSession, payment_id: str, provider_payment_id: Optional[str] = None) -> bool:
    """Подтвердить платёж и начислить кредиты."""
    payment = await get_payment(session, payment_id)
    
    if not payment or payment.status != "pending":
        return False
    
    payment.status = "completed"
    payment.completed_at = datetime.utcnow()
    
    if provider_payment_id:
        payment.provider_payment_id = provider_payment_id
    
    # Начисляем кредиты
    from src.services.users import update_balance
    await update_balance(session, payment.telegram_id, payment.credits)
    
    await session.commit()
    return True


async def cancel_payment(session: AsyncSession, payment_id: str) -> bool:
    """Отменить платёж."""
    payment = await get_payment(session, payment_id)
    
    if not payment or payment.status != "pending":
        return False
    
    payment.status = "cancelled"
    await session.commit()
    return True