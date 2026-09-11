"""merge_two_heads

Revision ID: fe10e4d9b8ea
Revises: b7f2e4a19c3d, c5909ddd17aa
Create Date: 2026-09-09 16:50:39.539363

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe10e4d9b8ea'
down_revision: Union[str, None] = ('b7f2e4a19c3d', 'c5909ddd17aa')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
