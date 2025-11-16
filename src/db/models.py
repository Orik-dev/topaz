"""Database models."""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, BigInteger, Integer, ForeignKey, DateTime, Numeric, Text, Boolean, func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    receipt_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    balance_credits: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rub_amount: Mapped[Numeric] = mapped_column(Numeric(10, 2))
    amount: Mapped[int] = mapped_column(Integer)  # кредиты
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    ext_payment_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    confirmation_url: Mapped[Optional[str]] = mapped_column(String(512))
    receipt_needed: Mapped[bool] = mapped_column(Boolean, default=True)
    receipt_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    task_type: Mapped[str] = mapped_column(String(20))  # 'image' или 'video'
    model_name: Mapped[str] = mapped_column(String(64))  # название модели Topaz
    status: Mapped[str] = mapped_column(String(32), default="queued")
    credits_cost: Mapped[int] = mapped_column(Integer, default=0)  # ожидаемая стоимость
    credits_used: Mapped[int] = mapped_column(Integer, default=0)  # фактически списано
    input_url: Mapped[Optional[str]] = mapped_column(Text)
    result_url: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class BroadcastJob(Base):
    __tablename__ = "broadcast_jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    fallback: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[Optional[str]] = mapped_column(Text)
    media_type: Mapped[Optional[str]] = mapped_column(String(20))
    media_file_id: Mapped[Optional[str]] = mapped_column(Text)