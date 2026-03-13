from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    USER = "USER"


class WipeJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole, native_enum=False), default=UserRole.OPERATOR)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WipeJob(Base):
    __tablename__ = "wipe_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    engine_job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device: Mapped[str] = mapped_column(String(255), index=True)
    device_type: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    device_serial_number: Mapped[str] = mapped_column(String(255), default="UNKNOWN")
    wipe_method: Mapped[str] = mapped_column(String(64))
    status: Mapped[WipeJobStatus] = mapped_column(SqlEnum(WipeJobStatus, native_enum=False), index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    bytes_wiped: Mapped[int] = mapped_column(Integer, default=0)
    overwrite_passes: Mapped[int] = mapped_column(Integer, default=0)
    execution_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recovered_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    certificate = relationship("Certificate", back_populates="job", uselist=False)


class DeviceLog(Base):
    __tablename__ = "devices_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device: Mapped[str] = mapped_column(String(255), index=True)
    device_type: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    size: Mapped[str] = mapped_column(String(64), default="0B")
    serial_number: Mapped[str] = mapped_column(String(255), default="UNKNOWN")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
