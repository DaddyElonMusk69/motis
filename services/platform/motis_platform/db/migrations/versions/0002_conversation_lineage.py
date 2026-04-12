"""Add conversation lineage fields for delegated child sessions

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple | None = None
depends_on: str | tuple | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("source", sa.String(32), nullable=False, server_default="chat"),
    )
    op.add_column(
        "conversations",
        sa.Column("parent_conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_conversations_source",
        "conversations",
        ["source"],
        unique=False,
    )
    op.create_index(
        "ix_conversations_parent_conversation_id",
        "conversations",
        ["parent_conversation_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_conversations_parent_conversation_id",
        "conversations",
        "conversations",
        ["parent_conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_parent_conversation_id",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index("ix_conversations_parent_conversation_id", table_name="conversations")
    op.drop_index("ix_conversations_source", table_name="conversations")
    op.drop_column("conversations", "parent_conversation_id")
    op.drop_column("conversations", "source")
