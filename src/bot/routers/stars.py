from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import User
from src.services.users import UserService
from src.services.pricing import get_package_info, calculate_stars_amount
from src.core.config import settings
from src.db.engine import async_session_maker
from src.services.telegram_safe import safe_answer, safe_send_text
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data.startswith("pay_stars:"))
async def pay_stars(callback: CallbackQuery, state: FSMContext):
    """Оплата через Telegram Stars"""
    logger.info(f"⭐ Stars payment initiated: user={callback.from_user.id}")
    
    package_id = callback.data.split(":")[1]
    package = get_package_info(package_id)
    
    total_gens = package["generations"] + package["bonus"]
    price_rub = package["price"]
    stars_amount = calculate_stars_amount(price_rub)
    
    await state.clear()
    
    # Удаляем сообщение с выбором
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")
    
    # Отправляем инвойс
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"{total_gens} генераций",
            description=f"Topaz AI Bot — пополнение на {total_gens} генераций",
            payload=f"stars:{package_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=f"{total_gens} генераций", amount=stars_amount)]
        )
        logger.info(
            f"✅ Stars invoice sent: user={callback.from_user.id}, "
            f"stars={stars_amount}, gens={total_gens}"
        )
    except TelegramForbiddenError:
        logger.warning(f"⚠️ Stars invoice forbidden: user={callback.from_user.id}")
        await safe_answer(callback, "❌ Не удалось отправить инвойс", show_alert=True)
    except Exception as e:
        logger.exception(f"❌ Stars invoice error: user={callback.from_user.id}, error={e}")
        await safe_answer(callback, "❌ Ошибка создания инвойса", show_alert=True)
    
    await safe_answer(callback)


@router.pre_checkout_query()
async def stars_pre_checkout(q: PreCheckoutQuery):
    """Pre-checkout для Stars"""
    logger.info(f"⭐ Pre-checkout: user={q.from_user.id}, payload={q.invoice_payload}")
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def stars_success(m: Message, state: FSMContext):
    """
    ✅ Успешная оплата Stars
    Полная защита от ошибок + идемпотентность + логирование
    """
    try:
        await state.clear()
        
        payload = m.successful_payment.invoice_payload or ""
        charge_id = m.successful_payment.telegram_payment_charge_id or ""
        
        logger.info(
            f"⭐ Payment received: user={m.from_user.id}, "
            f"payload={payload}, charge_id={charge_id}"
        )
        
        # Проверка формата payload
        if not payload.startswith("stars:"):
            logger.warning(f"⚠️ Invalid payload: user={m.from_user.id}, payload={payload}")
            return
        
        # Извлечение package_id
        try:
            package_id = payload.split(":", 1)[1]
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Parse error: user={m.from_user.id}, payload={payload}, error={e}")
            return
        
        # Получение пакета
        package = get_package_info(package_id)
        total_gens = package["generations"] + package["bonus"]
        
        # ✅ Идемпотентность через Redis
        idempotency_key = f"stars:paid:{charge_id}"
        redis = await aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB_CACHE
        )
        
        try:
            already_processed = await redis.exists(idempotency_key)
            if already_processed:
                logger.warning(
                    f"⚠️ Duplicate payment: user={m.from_user.id}, charge_id={charge_id}"
                )
                await safe_send_text(
                    m.bot,
                    m.chat.id,
                    "✅ Баланс уже был пополнен ранее."
                )
                return
            
            # Помечаем как обработанный (7 дней)
            await redis.setex(idempotency_key, 604800, "1")
            
        except Exception as e:
            logger.error(f"❌ Redis error: user={m.from_user.id}, error={e}")
        finally:
            try:
                await redis.aclose()
            except Exception:
                pass
        
        # Зачисление генераций
        async with async_session_maker() as session:
            try:
                result = await session.execute(
                    select(User).where(User.telegram_id == m.from_user.id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    logger.error(f"❌ User not found: user={m.from_user.id}")
                    await safe_send_text(
                        m.bot,
                        m.chat.id,
                        "❌ Ошибка: пользователь не найден.\n\nНапишите /start для регистрации"
                    )
                    return
                
                old_balance = user.balance
                
                # Начисляем генерации
                await UserService.add_credits(
                    session=session,
                    user=user,
                    amount=total_gens,
                    description=f"Пополнение через Stars: {package_id}",
                    reference_type="payment_stars"
                )
                await session.commit()
                
                logger.info(
                    f"✅ Balance updated: user={m.from_user.id}, "
                    f"package={package_id}, gens={total_gens}, "
                    f"old={old_balance}, new={user.balance}"
                )
                
                # Уведомление пользователю
                text = (
                    f"✅ <b>Оплата звёздами прошла!</b>\n\n"
                    f"💰 Баланс пополнен на <b>{int(total_gens)}</b> генераций.\n"
                    f"⚡ Текущий баланс: <b>{int(user.balance)}</b> генераций.\n\n"
                    f"Используйте /start для начала работы"
                )
                
                await safe_send_text(
                    m.bot,
                    m.chat.id,
                    text,
                    parse_mode="HTML"
                )
                
            except Exception as e:
                logger.exception(f"❌ DB error: user={m.from_user.id}, error={e}")
                
                error_text = (
                    "⚠️ <b>Ошибка при зачислении</b>\n\n"
                    "Платёж получен, но возникла ошибка при зачислении генераций.\n\n"
                    f"Напишите @{settings.SUPPORT_USERNAME} с скриншотом оплаты — "
                    "мы вручную пополним баланс!"
                )
                
                await safe_send_text(
                    m.bot,
                    m.chat.id,
                    error_text,
                    parse_mode="HTML"
                )
                
    except Exception as e:
        logger.exception(f"❌ Critical error: user={m.from_user.id}, error={e}")
        
        try:
            error_text = (
                "⚠️ <b>Произошла ошибка</b>\n\n"
                "Что-то пошло не так при обработке платежа.\n\n"
                f"Напишите @{settings.SUPPORT_USERNAME} с скриншотом — разберёмся!"
            )
            
            await safe_send_text(
                m.bot,
                m.chat.id,
                error_text,
                parse_mode="HTML"
            )
        except Exception:
            pass