"""Add assistant runtime metadata to conversation messages

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | tuple | None = None
depends_on: str | tuple | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("finish_reason", sa.String(32), nullable=True),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("reasoning", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("reasoning_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("codex_reasoning_items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "codex_reasoning_items")
    op.drop_column("conversation_messages", "reasoning_details")
    op.drop_column("conversation_messages", "reasoning")
    op.drop_column("conversation_messages", "finish_reason")
