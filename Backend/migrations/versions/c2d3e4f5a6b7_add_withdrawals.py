"""add withdrawals table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-11-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Member names (QUEUED/…), matching SQLAlchemy Enum(...) + Chain/QuoteKind migrations.
withdrawal_status = sa.Enum(
    "QUEUED",
    "SIGNED",
    "BROADCAST",
    "CONFIRMED",
    "FAILED_REFUNDED",
    "NEEDS_REVIEW",
    name="withdrawalstatus",
)
withdraw_asset = sa.Enum(
    "SOL",
    "USDC",
    name="withdrawasset",
)


def upgrade() -> None:
    withdrawal_status.create(op.get_bind(), checkfirst=True)
    withdraw_asset.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "withdrawals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "chain",
            sa.Enum("SOLANA", "POLYGON", name="chain", create_type=False),
            nullable=False,
        ),
        sa.Column("asset", withdraw_asset, nullable=False),
        sa.Column("credits_debited", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("net_atomic_amount", sa.BigInteger(), nullable=False),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("quote_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("status", withdrawal_status, nullable=False),
        sa.Column("nonce", sa.Integer(), nullable=True),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("attempt_hashes", sa.JSON(), nullable=True),
        sa.Column("raw_tx", sa.LargeBinary(), nullable=True),
        sa.Column("last_valid_block_height", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quote_id"], ["payment_quotes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id"),
        sa.UniqueConstraint("signature"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_withdrawals_user_idempotency",
        ),
    )
    op.create_index(op.f("ix_withdrawals_id"), "withdrawals", ["id"], unique=False)
    op.create_index(
        op.f("ix_withdrawals_user_id"), "withdrawals", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_withdrawals_quote_id"), "withdrawals", ["quote_id"], unique=False
    )
    op.create_index(
        "ix_withdrawals_status_created_at",
        "withdrawals",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_withdrawals_status_created_at", table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_quote_id"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_user_id"), table_name="withdrawals")
    op.drop_index(op.f("ix_withdrawals_id"), table_name="withdrawals")
    op.drop_table("withdrawals")
    withdraw_asset.drop(op.get_bind(), checkfirst=True)
    withdrawal_status.drop(op.get_bind(), checkfirst=True)
