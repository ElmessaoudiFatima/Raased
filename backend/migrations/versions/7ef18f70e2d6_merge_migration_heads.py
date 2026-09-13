"""merge migration heads

Revision ID: 7ef18f70e2d6
Revises: 9d0e6e98ddc6, f4408a2a08cb
Create Date: 2026-09-13 16:47:23.227430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7ef18f70e2d6'
down_revision: Union[str, None] = ('9d0e6e98ddc6', 'f4408a2a08cb')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
