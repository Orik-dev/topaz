from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Payment, User
from yookassa import Configuration, Payment as YooPayment
from src.core.config import settings
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

# Конфигурация YooKassa
Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


class PaymentService:
    """Сервис для работы с платежами"""
    
    @staticmethod
    async def create_yookassa_payment(
        session: AsyncSession,
        user: User,
        amount: float,
        credits: float,
        email: str = None
    ) -> dict:
        """
        Создать платеж через YooKassa
        """
        # Генерируем уникальный ID платежа
        idempotence_key = str(uuid4())
        
        # Используем email пользователя или дефолтный
        receipt_email = email or settings.DEFAULT_RECEIPT_EMAIL
        
        # Создаем платеж в YooKassa
        payment = YooPayment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": f"Пополнение баланса - {int(credits)} генераций",
            "metadata": {
                "user_id": str(user.id),
                "credits": str(credits)
            },
            "receipt": {
                "customer": {
                    "email": receipt_email
                },
                "items": [
                    {
                        "description": f"Пополнение баланса - {int(credits)} генераций",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1
                    }
                ]
            }
        }, idempotence_key)
        
        # Сохраняем платеж в БД
        db_payment = Payment(
            user_id=user.id,
            payment_id=payment.id,
            amount=amount,
            credits=credits,
            status="pending",
            payment_method="yookassa"
        )
        session.add(db_payment)
        await session.flush()
        
        logger.info(f"YooKassa payment created: user_id={user.id}, payment_id={payment.id}, amount={amount}")
        
        return {
            "payment_id": payment.id,
            "payment_url": payment.confirmation.confirmation_url,
            "amount": amount,
            "credits": credits
        }
    
    @staticmethod
    async def get_payment_by_id(
        session: AsyncSession,
        payment_id: str
    ) -> Payment:
        """Получить платеж по payment_id"""
        from sqlalchemy import select
        
        result = await session.execute(
            select(Payment).where(Payment.payment_id == payment_id)
        )
        return result.scalar_one_or_none()