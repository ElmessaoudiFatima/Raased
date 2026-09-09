"""merge migration heads (fork c5909ddd17aa + b7f2e4a19c3d)

Revision ID: a1b2c3d4e5f6
Revises: c5909ddd17aa, b7f2e4a19c3d
Create Date: 2026-09-09 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str]] = ('c5909ddd17aa', 'b7f2e4a19c3d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass