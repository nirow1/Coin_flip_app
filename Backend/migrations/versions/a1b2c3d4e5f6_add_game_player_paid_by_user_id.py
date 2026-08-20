"""Add game_players.paid_by_user_id

Revision ID: a1b2c3d4e5f6
Revises: 5fb2556c34e7
Create Date: 2026-08-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5fb2556c34e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "game_players",
        sa.Column("paid_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_game_players_paid_by_user_id",
        "game_players",
        "users",
        ["paid_by_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    # Backfill: assume seat holder paid (correct for self-joins; invites stay imperfect).
    op.execute("UPDATE game_players SET paid_by_user_id = user_id WHERE paid_by_user_id IS NULL")


def downgrade():
    op.drop_constraint("fk_game_players_paid_by_user_id", "game_players", type_="foreignkey")
    op.drop_column("game_players", "paid_by_user_id")
