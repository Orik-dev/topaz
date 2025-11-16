from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Payment, PaymentStatus, User
from src.services.users import UserService
from yookassa import Configuration, Payment as YooPayment
from src.core.config import settings
from typing import Optional
from sqlalchemy import select
import logging
import uuid

logger = logging.getLogger(__name__)

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


class PaymentService:
    @staticmethod
    async def create_payment(
        session: AsyncSession,
        user: User,
        amount: float,
        credits: float,
        payment_method: str = "yookassa"
    ) -> Payment:
        """Создать платеж"""
        payment_id = str(uuid.uuid4())

        payment = Payment(
            user_id=user.id,
            payment_id=payment_id,
            amount=amount,
            credits=credits,
            status=PaymentStatus.PENDING,
            payment_method=payment_method
        )
        session.add(payment)
        await session.flush()
        return payment

    @staticmethod
    async def create_yookassa_payment(
        session: AsyncSession,
        user: User,
        amount: float,
        credits: float
    ) -> dict:
        """Создать YooKassa платеж (с email, БЕЗ чека!)"""
        payment = await PaymentService.create_payment(
            session=session,
            user=user,
            amount=amount,
            credits=credits,
            payment_method="yookassa"
        )

        try:
            # Создаем платеж (email отправляется, НО чек не обязателен!)
            yoo_payment = YooPayment.create({
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": settings.YOOKASSA_RETURN_URL
                },
                "capture": True,
                "description": f"Пополнение {int(credits)} генераций",
                "metadata": {
                    "user_id": user.id,
                    "payment_id": payment.payment_id,
                    "telegram_id": user.telegram_id
                },
                "receipt": {
                    "customer": {
                        "email": settings.DEFAULT_RECEIPT_EMAIL  # Email для ИП
                    },
                    "items": [{
                        "description": f"{int(credits)} генераций",
                        "quantity": "1.00",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1
                    }]
                }
            })

            payment.metadata = yoo_payment.id
            await session.flush()
            await session.commit()

            return {
                "payment_url": yoo_payment.confirmation.confirmation_url,
                "payment_id": payment.payment_id
            }

        except Exception as e:
            logger.error(f"YooKassa payment creation error: {e}", exc_info=True)
            raise

    @staticmethod
    async def process_yookassa_webhook(session: AsyncSession, yookassa_payment_id: str) -> bool:
        """Обработать YooKassa webhook"""
        try:
            yoo_payment = YooPayment.find_one(yookassa_payment_id)

            result = await session.execute(
                select(Payment).where(Payment.metadata == yookassa_payment_id)
            )
            payment = result.scalar_one_or_none()

            if not payment:
                logger.error(f"Payment not found: {yookassa_payment_id}")
                return False

            if payment.status == PaymentStatus.SUCCEEDED:
                return True

            if yoo_payment.status == "succeeded":
                payment.status = PaymentStatus.SUCCEEDED
                await session.flush()

                user = await session.get(User, payment.user_id)
                await UserService.add_credits(
                    session=session,
                    user=user,
                    amount=payment.credits,
                    description=f"Пополнение через YooKassa",
                    reference_type="payment",
                    reference_id=payment.id
                )
                await session.commit()
                logger.info(f"Payment {payment.payment_id} succeeded")
                return True

            elif yoo_payment.status == "canceled":
                payment.status = PaymentStatus.CANCELED
                await session.flush()
                await session.commit()

            return False

        except Exception as e:
            logger.error(f"YooKassa webhook error: {e}", exc_info=True)
            return False