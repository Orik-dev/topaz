from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.db.models import User, CreditLedger
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """
        Получить или создать пользователя
        ✅ С начислением бонуса при регистрации
        """
        # Ищем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Обновляем данные если изменились
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            
            if updated:
                await session.flush()
                logger.info(f"User updated: telegram_id={telegram_id}")
            
            return user
        
        # Создаем нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            balance=5.0  # ✅ Бонус при регистрации
        )
        
        session.add(user)
        await session.flush()
        await session.refresh(user)
        
        # ✅ Записываем бонус в историю
        ledger_entry = CreditLedger(
            user_id=user.id,
            amount=5.0,
            balance_after=5.0,
            description="Бонус при регистрации",
            reference_type="bonus",
            reference_id=None
        )
        session.add(ledger_entry)
        await session.flush()
        
        logger.info(f"New user created: telegram_id={telegram_id}, bonus=5.0")
        
        return user
    
    @staticmethod
    async def add_credits(
        session: AsyncSession,
        user: User,
        amount: float,
        description: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None
    ) -> bool:
        """
        Добавить генерации пользователю
        ✅ Атомарная операция с записью в историю
        """
        if amount <= 0:
            logger.warning(f"Invalid amount for add_credits: user_id={user.id}, amount={amount}")
            return False
        
        try:
            # Обновляем баланс
            old_balance = user.balance
            user.balance += amount
            
            await session.flush()
            
            # Записываем в историю
            ledger_entry = CreditLedger(
                user_id=user.id,
                amount=amount,
                balance_after=user.balance,
                description=description,
                reference_type=reference_type,
                reference_id=reference_id
            )
            session.add(ledger_entry)
            
            await session.flush()
            
            logger.info(
                f"Credits added: user_id={user.id}, amount={amount}, "
                f"old_balance={old_balance}, new_balance={user.balance}, "
                f"description={description}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding credits: user_id={user.id}, error={e}", exc_info=True)
            return False
    
    @staticmethod
    async def deduct_credits(
        session: AsyncSession,
        user: User,
        amount: float,
        description: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None
    ) -> bool:
        """
        Списать генерации у пользователя
        ✅ С проверкой баланса
        ✅ Атомарная операция с записью в историю
        """
        if amount <= 0:
            logger.warning(f"Invalid amount for deduct_credits: user_id={user.id}, amount={amount}")
            return False
        
        # Проверяем баланс
        if user.balance < amount:
            logger.warning(
                f"Insufficient balance: user_id={user.id}, "
                f"balance={user.balance}, required={amount}"
            )
            return False
        
        try:
            # Списываем
            old_balance = user.balance
            user.balance -= amount
            
            await session.flush()
            
            # Записываем в историю (отрицательная сумма)
            ledger_entry = CreditLedger(
                user_id=user.id,
                amount=-amount,  # ✅ Отрицательная сумма
                balance_after=user.balance,
                description=description,
                reference_type=reference_type,
                reference_id=reference_id
            )
            session.add(ledger_entry)
            
            await session.flush()
            
            logger.info(
                f"Credits deducted: user_id={user.id}, amount={amount}, "
                f"old_balance={old_balance}, new_balance={user.balance}, "
                f"description={description}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deducting credits: user_id={user.id}, error={e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_user_by_telegram_id(
        session: AsyncSession,
        telegram_id: int
    ) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(
        session: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """Получить пользователя по ID"""
        return await session.get(User, user_id)
    
    @staticmethod
    async def get_credit_history(
        session: AsyncSession,
        user: User,
        limit: int = 50
    ) -> list[CreditLedger]:
        """
        Получить историю операций с генерациями
        """
        result = await session.execute(
            select(CreditLedger)
            .where(CreditLedger.user_id == user.id)
            .order_by(CreditLedger.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_balance(
        session: AsyncSession,
        telegram_id: int
    ) -> float:
        """Получить баланс пользователя"""
        user = await UserService.get_user_by_telegram_id(session, telegram_id)
        return user.balance if user else 0.0
    
    @staticmethod
    async def set_balance(
        session: AsyncSession,
        user: User,
        new_balance: float,
        description: str = "Установка баланса админом"
    ) -> bool:
        """
        Установить конкретный баланс (для админа)
        ✅ С записью в историю
        """
        if new_balance < 0:
            logger.warning(f"Invalid balance: user_id={user.id}, balance={new_balance}")
            return False
        
        try:
            old_balance = user.balance
            difference = new_balance - old_balance
            
            user.balance = new_balance
            await session.flush()
            
            # Записываем изменение в историю
            ledger_entry = CreditLedger(
                user_id=user.id,
                amount=difference,
                balance_after=new_balance,
                description=description,
                reference_type="admin_adjustment",
                reference_id=None
            )
            session.add(ledger_entry)
            await session.flush()
            
            logger.info(
                f"Balance set: user_id={user.id}, "
                f"old_balance={old_balance}, new_balance={new_balance}, "
                f"difference={difference}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting balance: user_id={user.id}, error={e}", exc_info=True)
            return False
    
    @staticmethod
    async def get_all_users(
        session: AsyncSession,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> list[User]:
        """
        Получить всех пользователей (для админа)
        """
        query = select(User).order_by(User.created_at.desc())
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_active_users_count(session: AsyncSession) -> int:
        """Получить количество активных пользователей (баланс > 0)"""
        result = await session.execute(
            select(User).where(User.balance > 0)
        )
        return len(list(result.scalars().all()))
    
    @staticmethod
    async def get_total_balance(session: AsyncSession) -> float:
        """Получить общий баланс всех пользователей"""
        result = await session.execute(select(User))
        users = result.scalars().all()
        return sum(user.balance for user in users)