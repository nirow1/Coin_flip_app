"""Add discriminator column

Revision ID: 5fb2556c34e7
Revises: 02b720080fc5
Create Date: 2026-07-06 15:51:16.260159

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fb2556c34e7'
down_revision: Union[str, Sequence[str], None] = '02b720080fc5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('discriminator', sa.String(length=4), nullable=False, server_default='0000')
    )
    op.create_unique_constraint(
        'uq_username_disc',
        'users',
        ['username', 'discriminator']
    )

def downgrade():
    op.drop_constraint('uq_username_disc', 'users', type_='unique')
    op.drop_column('users', 'discriminator')
