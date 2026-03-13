from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("wipe_jobs.id"), unique=True, index=True)
    device: Mapped[str] = mapped_column(String(255))
    device_serial_number: Mapped[str] = mapped_column(String(255), default="UNKNOWN")
    device_type: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    wipe_method: Mapped[str] = mapped_column(String(64))
    overwrite_passes: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verification_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    recovered_files: Mapped[int] = mapped_column(Integer, default=0)
    sha256_hash: Mapped[str] = mapped_column(String(128), default="")
    verification_url: Mapped[str] = mapped_column(String(512), default="")
    json_path: Mapped[str] = mapped_column(String(512), default="")
    pdf_path: Mapped[str] = mapped_column(String(512), default="")
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job = relationship("WipeJob", back_populates="certificate")
