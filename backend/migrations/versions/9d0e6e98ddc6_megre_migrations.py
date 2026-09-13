"""megre migrations

Revision ID: 9d0e6e98ddc6
Revises: 207edae1d651, a1b2c3d4e5f6, acd9eba7b362, b452f7826642
Create Date: 2026-09-11 14:36:05.123080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d0e6e98ddc6'
down_revision: Union[str, None] = ('207edae1d651', 'a1b2c3d4e5f6', 'acd9eba7b362', 'b452f7826642')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
