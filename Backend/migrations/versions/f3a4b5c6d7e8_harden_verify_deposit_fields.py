"""harden verify deposit fields on credit_orders / unmatched_deposits

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-10-19 16:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "credit_orders",
        sa.Column("received_atomic_amount", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "credit_orders",
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_credit_orders_user_id_status",
        "credit_orders",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_credit_orders_status_expires_at",
        "credit_orders",
        ["status", "expires_at"],
        unique=False,
    )

    op.add_column(
        "unmatched_deposits",
        sa.Column("sender", sa.String(), nullable=True),
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column(
            "chain",
            sa.Enum("SOLANA", "POLYGON", name="chain", create_type=False),
            nullable=False,
            server_default="SOLANA",
        ),
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column("reference_pubkey", sa.String(), nullable=True),
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column("block_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column("resolved_order_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_unmatched_deposits_resolved_order_id",
        "unmatched_deposits",
        "credit_orders",
        ["resolved_order_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_unmatched_deposits_resolved_order_id",
        "unmatched_deposits",
        type_="foreignkey",
    )
    op.drop_column("unmatched_deposits", "resolved_order_id")
    op.drop_column("unmatched_deposits", "block_time")
    op.drop_column("unmatched_deposits", "reference_pubkey")
    op.drop_column("unmatched_deposits", "chain")
    op.drop_column("unmatched_deposits", "sender")

    op.drop_index("ix_credit_orders_status_expires_at", table_name="credit_orders")
    op.drop_index("ix_credit_orders_user_id_status", table_name="credit_orders")
    op.drop_column("credit_orders", "paid_at")
    op.drop_column("credit_orders", "received_atomic_amount")
