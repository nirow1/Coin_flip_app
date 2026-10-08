"""Add payment_quotes, credit_orders, unmatched_deposits

Revision ID: d7e8f9a0b1c2
Revises: c4d5e6f7a8b9
Create Date: 2026-10-08 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "payment_quotes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_quotes_user_id"),
        "payment_quotes",
        ["user_id"],
        unique=False,
    )

    chain_enum = sa.Enum("SOLANA", "POLYGON", name="chain")
    credit_order_status_enum = sa.Enum(
        "PENDING",
        "PAID",
        "EXPIRED",
        "NEEDS_REVIEW",
        name="creditorderstatus",
    )
    unmatched_deposit_status_enum = sa.Enum(
        "OPEN",
        "RESOLVED",
        "REFUNDED",
        name="unmatcheddepositstatus",
    )

    op.create_table(
        "credit_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("chain", chain_enum, nullable=False),
        sa.Column(
            "status",
            credit_order_status_enum,
            nullable=False,
        ),
        sa.Column("order_ref", sa.String(), nullable=False),
        sa.Column("reference_pubkey", sa.String(), nullable=False),
        sa.Column("quoted_atomic_amount", sa.BigInteger(), nullable=False),
        sa.Column("receive_address", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_tx_hash", sa.String(), nullable=True),
        sa.Column("quote_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["quote_id"], ["payment_quotes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_ref"),
        sa.UniqueConstraint("paid_tx_hash"),
        sa.UniqueConstraint("reference_pubkey"),
    )
    op.create_index(
        op.f("ix_credit_orders_id"),
        "credit_orders",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_orders_quote_id"),
        "credit_orders",
        ["quote_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_orders_user_id"),
        "credit_orders",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "unmatched_deposits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tx_hash", sa.String(), nullable=False),
        sa.Column("lamports", sa.BigInteger(), nullable=False),
        sa.Column("raw_memo", sa.String(), nullable=True),
        sa.Column(
            "status",
            unmatched_deposit_status_enum,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_hash"),
    )
    op.create_index(
        op.f("ix_unmatched_deposits_id"),
        "unmatched_deposits",
        ["id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_unmatched_deposits_id"), table_name="unmatched_deposits")
    op.drop_table("unmatched_deposits")
    op.drop_index(op.f("ix_credit_orders_user_id"), table_name="credit_orders")
    op.drop_index(op.f("ix_credit_orders_quote_id"), table_name="credit_orders")
    op.drop_index(op.f("ix_credit_orders_id"), table_name="credit_orders")
    op.drop_table("credit_orders")
    op.drop_index(op.f("ix_payment_quotes_user_id"), table_name="payment_quotes")
    op.drop_table("payment_quotes")

    sa.Enum(name="unmatcheddepositstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="creditorderstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="chain").drop(op.get_bind(), checkfirst=True)
