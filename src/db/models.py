from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime, Text, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

Base = declarative_base()


class TaskType(str, Enum):
    IMAGE_ENHANCE = "image_enhance"
    VIDEO_ENHANCE = "video_enhance"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class CreditLedger(Base):
    """История операций с генерациями"""
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)  # Положительное = начисление, отрицательное = списание
    balance_after = Column(Float, nullable=False)
    description = Column(String(500), nullable=False)
    reference_type = Column(String(50), nullable=True)  # payment, task, refund, bonus, etc.
    reference_id = Column(Integer, nullable=True)  # ID связанной записи
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(String(255), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    credits = Column(Float, nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    payment_method = Column(String(50), nullable=True)  # yookassa, stars
    created_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True)
    cost = Column(Float, nullable=False)
    model = Column(String(100), nullable=False)
    input_file_id = Column(String(255), nullable=True)
    output_file_url = Column(Text, nullable=True)
    topaz_request_id = Column(String(255), nullable=True, index=True)
    parameters = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)


class Broadcast(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_text = Column(Text, nullable=False)
    total_users = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)