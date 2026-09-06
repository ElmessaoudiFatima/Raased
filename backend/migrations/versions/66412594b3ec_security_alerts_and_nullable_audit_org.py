"""security alerts table and nullable audit_logs.organization_id

Revision ID: 66412594b3ec
Revises: 4ed9083ef452
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66412594b3ec'
down_revision: Union[str, None] = '4ed9083ef452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'security_alerts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('tracker_id', sa.UUID(), nullable=False),
        sa.Column('security_check_id', sa.UUID(), nullable=True),
        sa.Column('check_type', sa.String(length=30), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['tracker_id'], ['trackers.id'], ),
        sa.ForeignKeyConstraint(['security_check_id'], ['security_checks.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_security_alerts_organization_id', 'security_alerts', ['organization_id'])
    op.create_index('ix_security_alerts_tracker_id', 'security_alerts', ['tracker_id'])
    op.create_index('ix_security_alerts_status', 'security_alerts', ['status'])

    op.alter_column(
        'audit_logs',
        'organization_id',
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'audit_logs',
        'organization_id',
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.drop_index('ix_security_alerts_status', table_name='security_alerts')
    op.drop_index('ix_security_alerts_tracker_id', table_name='security_alerts')
    op.drop_index('ix_security_alerts_organization_id', table_name='security_alerts')
    op.drop_table('security_alerts')
