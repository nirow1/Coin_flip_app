"""drop user_solana_wallets; add WITHDRAWAL transaction type

Revision ID: e1f2a3b4c5d6
Revises: 0bdb71de778c
Create Date: 2026-10-19 15:40:00.000000

Before dropping user_solana_wallets: if any rows exist, fail so ops can sweep
on-chain balances from those public keys first.

Also refuse if legacy DEPOSIT_SOLANA / WITHDRAW_SOLANA transaction rows remain —
those enum members were removed from Python and would crash GET /wallet/transactions.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "0bdb71de778c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # sa.inspect / row counts need a live connection — skip in --sql offline mode.
    if not context.is_offline_mode():
        inspector = sa.inspect(bind)

        if "user_solana_wallets" in inspector.get_table_names():
            count = bind.execute(sa.text("SELECT count(*) FROM user_solana_wallets")).scalar()
            if count and int(count) > 0:
                rows = bind.execute(
                    sa.text("SELECT id, user_id, public_key FROM user_solana_wallets")
                ).fetchall()
                keys = ", ".join(f"{r.public_key} (user_id={r.user_id})" for r in rows)
                raise RuntimeError(
                    "Refusing to drop user_solana_wallets while rows exist. "
                    f"Sweep on-chain funds from these keys first, then re-run: {keys}"
                )
            op.drop_table("user_solana_wallets")

        if "transactions" in inspector.get_table_names():
            legacy = bind.execute(
                sa.text(
                    "SELECT count(*) FROM transactions "
                    "WHERE type::text IN ('DEPOSIT_SOLANA', 'WITHDRAW_SOLANA')"
                )
            ).scalar()
            if legacy and int(legacy) > 0:
                raise RuntimeError(
                    "Refusing to continue while legacy DEPOSIT_SOLANA / WITHDRAW_SOLANA "
                    f"transaction rows exist ({int(legacy)}). Remap or delete them first "
                    "(e.g. UPDATE to CREDIT / DEBIT), then re-run."
                )
    else:
        # Offline SQL scripts: emit the drop unconditionally.
        op.drop_table("user_solana_wallets")

    # Add WITHDRAWAL; leave legacy DEPOSIT_SOLANA / WITHDRAW_SOLANA values in PG unused.
    op.execute(sa.text("ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS 'WITHDRAWAL'"))


def downgrade() -> None:
    op.create_table(
        "user_solana_wallets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("private_key_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    # PostgreSQL cannot remove enum values safely; WITHDRAWAL remains.
