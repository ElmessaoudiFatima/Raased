"""merge migrations heads

Revision ID: 207edae1d651
Revises: b7f2e4a19c3d, c5909ddd17aa
Create Date: 2026-09-08 23:32:32.566312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '207edae1d651'
down_revision: Union[str, None] = ('b7f2e4a19c3d', 'c5909ddd17aa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
