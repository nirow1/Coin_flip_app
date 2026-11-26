"""harden_payment_quotes

Revision ID: 0bdb71de778c
Revises: d7e8f9a0b1c2
Create Date: 2026-10-19 14:21:11.297126

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "0bdb71de778c"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if not context.is_offline_mode():
        quote_count = bind.execute(sa.text("SELECT count(*) FROM payment_quotes")).scalar()
        if quote_count and int(quote_count) > 0:
            raise RuntimeError(
                "Refusing to add NOT NULL kind/chain on payment_quotes while rows exist "
                f"({int(quote_count)}). Backfill or truncate payment_quotes, then re-run."
            )
        null_quote_ids = bind.execute(
            sa.text("SELECT count(*) FROM credit_orders WHERE quote_id IS NULL")
        ).scalar()
        if null_quote_ids and int(null_quote_ids) > 0:
            raise RuntimeError(
                "Refusing to set credit_orders.quote_id NOT NULL while NULL rows exist "
                f"({int(null_quote_ids)}). Backfill quote_id, then re-run."
            )

    # Member names (BUY/WITHDRAW), matching SQLAlchemy Enum(QuoteKind) + existing
    # TransactionType / Chain migrations in this repo.
    quote_kind = sa.Enum("BUY", "WITHDRAW", name="quotekind")
    quote_kind.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "payment_quotes",
        sa.Column("kind", quote_kind, nullable=False),
    )
    op.add_column(
        "payment_quotes",
        sa.Column(
            "chain",
            sa.Enum("SOLANA", "POLYGON", name="chain", create_type=False),
            nullable=False,
        ),
    )
    op.add_column(
        "payment_quotes",
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Safe when credit_orders.quote_id has no NULLs (empty/dev DB).
    op.alter_column(
        "credit_orders",
        "quote_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.drop_index("ix_credit_orders_quote_id", table_name="credit_orders")
    op.create_index(
        "ix_credit_orders_quote_id",
        "credit_orders",
        ["quote_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_credit_orders_quote_id", table_name="credit_orders")
    op.create_index(
        "ix_credit_orders_quote_id",
        "credit_orders",
        ["quote_id"],
        unique=False,
    )
    op.alter_column(
        "credit_orders",
        "quote_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )

    op.drop_column("payment_quotes", "consumed_at")
    op.drop_column("payment_quotes", "chain")
    op.drop_column("payment_quotes", "kind")

    sa.Enum(name="quotekind").drop(op.get_bind(), checkfirst=True)
