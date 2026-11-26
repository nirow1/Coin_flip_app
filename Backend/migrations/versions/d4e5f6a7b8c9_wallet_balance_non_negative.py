"""CHECK (balance >= 0) on wallets

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-11-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_wallets_balance_non_negative",
        "wallets",
        "balance >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_wallets_balance_non_negative",
        "wallets",
        type_="check",
    )
