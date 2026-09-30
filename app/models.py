"""Модели проверок и метаданных загруженных файлов."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.schemas import CheckStatus


class Base(DeclarativeBase):
    pass


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    record_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=CheckStatus.IN_PROGRESS.value
    )
    status_label: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default="Проверка выполняется"
    )
    reason: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    issues: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    extracted: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    documents: Mapped[list["CheckDocument"]] = relationship(
        back_populates="check", cascade="all, delete-orphan", order_by="CheckDocument.position"
    )


class CheckDocument(Base):
    __tablename__ = "check_documents"
    __table_args__ = (
        UniqueConstraint("check_id", "position", name="uq_check_documents_check_position"),
        CheckConstraint("size_bytes >= 0", name="ck_check_documents_size_bytes_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    check_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("checks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    detected_type: Mapped[str | None] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    check: Mapped[Check] = relationship(back_populates="documents")
