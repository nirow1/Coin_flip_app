"""admin review audit fields + credit_orders.refunded + review_reason

Revision ID: b1c2d3e4f5a6
Revises: a9c0d1e2f3b4
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "a9c0d1e2f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("ALTER TYPE creditorderstatus ADD VALUE IF NOT EXISTS 'REFUNDED'")
    )
    op.add_column(
        "credit_orders",
        sa.Column("review_reason", sa.String(), nullable=True),
    )
    op.add_column(
        "credit_orders",
        sa.Column("resolved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "credit_orders",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_credit_orders_resolved_by",
        "credit_orders",
        "users",
        ["resolved_by"],
        ["id"],
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column("resolved_by", sa.Integer(), nullable=True),
    )
    op.add_column(
        "unmatched_deposits",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_unmatched_deposits_resolved_by",
        "unmatched_deposits",
        "users",
        ["resolved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_unmatched_deposits_resolved_by",
        "unmatched_deposits",
        type_="foreignkey",
    )
    op.drop_column("unmatched_deposits", "resolved_at")
    op.drop_column("unmatched_deposits", "resolved_by")
    op.drop_constraint(
        "fk_credit_orders_resolved_by",
        "credit_orders",
        type_="foreignkey",
    )
    op.drop_column("credit_orders", "resolved_at")
    op.drop_column("credit_orders", "resolved_by")
    op.drop_column("credit_orders", "review_reason")
    # PG cannot remove enum values; REFUNDED stays on creditorderstatus
