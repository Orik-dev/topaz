from uuid import uuid4
import logging
from typing import Optional
import asyncio
from functools import partial

from yookassa import Configuration, Payment
from yookassa.domain.exceptions.api_error import ApiError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.engine import async_session_maker
from src.db.models import Payment as PaymentModel, User
from src.services.users import UserService

logger = logging.getLogger(__name__)

Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

TECH_EMAIL = settings.DEFAULT_RECEIPT_EMAIL
YOOKASSA_TAX_SYSTEM_CODE = 2  # УСН доход
YOOKASSA_VAT_CODE = 1  # НДС не облагается
YOOKASSA_TIMEOUT = 15  # секунд


def _assert_yookassa_creds():
    """Проверка credentials YooKassa"""
    if not (settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY):
        raise RuntimeError("YooKassa credentials missing")


def validate_email(email: str) -> Optional[str]:
    """
    ✅ ПОЛНАЯ валидация email для YooKassa
    """
    if not email:
        return None
    
    email = email.strip()
    
    if len(email) < 6 or len(email) > 128:
        return None
    
    if any(c in email for c in [' ', '\t', '\n', '\r']):
        return None
    
    if "@" not in email or len(email) < 5:
        return None
    
    parts = email.split("@")
    if len(parts) != 2:
        return None
    
    local_part, domain_part = parts
    
    if not local_part or len(local_part) < 1:
        return None
    
    if local_part.startswith(".") or local_part.endswith("."):
        return None
    
    if "." not in domain_part:
        return None
    
    if domain_part.startswith(".") or domain_part.endswith("."):
        return None
    
    domain_parts = domain_part.split(".")
    if any(len(part) < 1 for part in domain_parts):
        return None
    
    if len(domain_parts[-1]) < 2:
        return None
    
    if "," in email:
        return None
    
    try:
        email.encode('ascii')
    except UnicodeEncodeError:
        return None
    
    forbidden_chars = ['<', '>', '(', ')', '[', ']', '\\', ',', ';', ':', '"', ' ']
    if any(char in local_part for char in forbidden_chars):
        return None
    
    return email.lower()


def _build_receipt(email: str, plan: str, amount_rub: float) -> dict:
    """Создание чека для YooKassa"""
    return {
        "customer": {"email": email.strip()},
        "items": [
            {
                "description": f"Тариф {plan}"[:128],
                "quantity": "1.00",
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "vat_code": int(YOOKASSA_VAT_CODE),
                "payment_subject": "service",
                "payment_mode": "full_prepayment",
                "measure": "piece",
            }
        ],
        "tax_system_code": int(YOOKASSA_TAX_SYSTEM_CODE),
    }


def _create_payment_sync(body: dict, idem_key: str) -> Payment:
    """
    ✅ Синхронная обёртка для Payment.create с timeout
    """
    import requests
    
    original_request = requests.Session.request
    
    def request_with_timeout(self, method, url, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = YOOKASSA_TIMEOUT
        return original_request(self, method, url, **kwargs)
    
    requests.Session.request = request_with_timeout
    
    try:
        payment = Payment.create(body, idem_key)
        return payment
    finally:
        requests.Session.request = original_request


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
        ✅ С timeout, валидацией email, обработкой ошибок
        """
        _assert_yookassa_creds()
        
        # Определяем email для чека
        if email and not getattr(user, 'receipt_opt_out', False):
            validated_email = validate_email(email)
            
            if validated_email:
                receipt_email = validated_email
                logger.info(f"Payment with user email: user={user.telegram_id}, email={receipt_email}")
            else:
                receipt_email = TECH_EMAIL
                logger.warning(f"Invalid user email, using tech: user={user.telegram_id}")
        else:
            receipt_email = TECH_EMAIL
            logger.info(f"Payment with tech email: user={user.telegram_id}")
        
        # Создаем запись в БД
        db_payment = PaymentModel(
            user_id=user.id,
            payment_id="",  # Заполнится после создания
            amount=amount,
            credits=credits,
            status="pending",
            payment_method="yookassa"
        )
        session.add(db_payment)
        await session.flush()
        await session.refresh(db_payment)
        
        # Данные для YooKassa
        description = f"Topaz AI Bot - {int(credits)} генераций"[:128]
        plan = f"{int(amount)} ₽ → {int(credits)} генераций"
        receipt = _build_receipt(email=receipt_email, plan=plan, amount_rub=amount)
        
        body = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": str(user.id),
                "telegram_id": str(user.telegram_id),
                "credits": str(credits)
            },
            "receipt": receipt,
        }
        
        idem_key = str(uuid4())
        
        logger.info(
            f"Creating YooKassa payment: amount={amount}, "
            f"receipt_email={receipt_email}, timeout={YOOKASSA_TIMEOUT}s"
        )
        
        try:
            # ✅ Запуск с timeout
            loop = asyncio.get_event_loop()
            payment_task = loop.run_in_executor(
                None,
                partial(_create_payment_sync, body, idem_key)
            )
            
            payment = await asyncio.wait_for(payment_task, timeout=YOOKASSA_TIMEOUT + 2)
            
        except asyncio.TimeoutError:
            logger.error(f"YooKassa Timeout: user={user.telegram_id}, timeout={YOOKASSA_TIMEOUT}s")
            
            # Помечаем платеж как failed
            db_payment.status = "failed"
            await session.flush()
            
            raise RuntimeError(f"YooKassa timeout after {YOOKASSA_TIMEOUT}s")
            
        except ApiError as e:
            logger.error(
                f"YooKassa ApiError: type={getattr(e, 'type', None)}, "
                f"code={getattr(e, 'code', None)}, "
                f"desc={getattr(e, 'description', str(e))}, "
                f"receipt_email={receipt_email}"
            )
            
            db_payment.status = "failed"
            await session.flush()
            
            raise RuntimeError(f"YooKassa API error: {getattr(e, 'description', str(e))}")
            
        except Exception as e:
            error_str = str(e).lower()
            
            if any(code in error_str for code in ['500', '502', '503', '504', 'server error', 'bad gateway']):
                logger.error(f"YooKassa server error: user={user.telegram_id}, error={e}")
                
                db_payment.status = "failed"
                await session.flush()
                
                raise RuntimeError("YooKassa server unavailable")
            
            if 'timeout' in error_str or 'timed out' in error_str:
                logger.error(f"YooKassa timeout in exception: user={user.telegram_id}, error={e}")
                
                db_payment.status = "failed"
                await session.flush()
                
                raise RuntimeError("YooKassa timeout")
            
            logger.exception(f"YooKassa unknown error: user={user.telegram_id}")
            
            db_payment.status = "failed"
            await session.flush()
            
            raise RuntimeError(f"YooKassa error: {str(e)[:100]}")
        
        # Обновляем payment_id
        db_payment.payment_id = payment.id
        await session.flush()
        
        logger.info(f"✅ Payment created: user={user.telegram_id}, payment_id={payment.id}")
        
        return {
            "payment_id": payment.id,
            "payment_url": payment.confirmation.confirmation_url,
            "amount": amount,
            "credits": credits
        }
    
    @staticmethod
    async def get_payment_by_id(session: AsyncSession, payment_id: str) -> PaymentModel:
        """Получить платеж по payment_id"""
        result = await session.execute(
            select(PaymentModel).where(PaymentModel.payment_id == payment_id)
        )
        return result.scalar_one_or_none()