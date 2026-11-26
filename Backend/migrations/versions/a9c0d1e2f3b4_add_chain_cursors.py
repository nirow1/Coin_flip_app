"""add_chain_cursors

Revision ID: a9c0d1e2f3b4
Revises: f3a4b5c6d7e8
Create Date: 2026-10-29 13:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c0d1e2f3b4"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chain_cursors",
        sa.Column(
            "chain",
            sa.Enum("SOLANA", "POLYGON", name="chain", create_type=False),
            primary_key=True,
        ),
        sa.Column("last_signature", sa.String(), nullable=True),
        sa.Column("last_block", sa.BigInteger(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("chain_cursors")
