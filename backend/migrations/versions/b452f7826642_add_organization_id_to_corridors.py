"""add_organization_id_to_corridors

Revision ID: b452f7826642
Revises: fe10e4d9b8ea
Create Date: 2026-09-09 16:50:55.513429
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b452f7826642'
down_revision: Union[str, None] = 'fe10e4d9b8ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add optional organization_id FK to corridors
    op.add_column('corridors', sa.Column('organization_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_corridors_organization_id'), 'corridors', ['organization_id'], unique=False)
    op.create_foreign_key(None, 'corridors', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    # Remove organization_id FK from corridors
    op.drop_constraint(None, 'corridors', type_='foreignkey')
    op.drop_index(op.f('ix_corridors_organization_id'), table_name='corridors')
    op.drop_column('corridors', 'organization_id')
