"""Начальные таблицы проверок и файлов.

Revision ID: 20260930_01
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260930_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("record_type", sa.String(length=16), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="check_in_progress", nullable=False
        ),
        sa.Column(
            "status_label",
            sa.String(length=128),
            server_default="Проверка выполняется",
            nullable=False,
        ),
        sa.Column("reason", sa.String(), server_default="", nullable=False),
        sa.Column(
            "issues", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "extracted", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "check_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("check_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("detected_type", sa.String(length=32), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="ck_check_documents_size_bytes_nonnegative"),
        sa.ForeignKeyConstraint(["check_id"], ["checks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("check_id", "position", name="uq_check_documents_check_position"),
    )
    op.create_index("ix_check_documents_check_id", "check_documents", ["check_id"])


def downgrade() -> None:
    op.drop_index("ix_check_documents_check_id", table_name="check_documents")
    op.drop_table("check_documents")
    op.drop_table("checks")
