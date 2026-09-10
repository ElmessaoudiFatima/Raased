"""weather snapshots table + optional link from risk_assessments

Revision ID: acd9eba7b362
Revises: b7f2e4a19c3d
Create Date: 2026-09-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acd9eba7b362'
down_revision: Union[str, None] = 'b7f2e4a19c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'weather_snapshots',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('corridor_id', sa.UUID(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('wind_speed_kmh', sa.Float(), nullable=True),
        sa.Column('visibility_m', sa.Float(), nullable=True),
        sa.Column('weather_code', sa.Integer(), nullable=True),
        sa.Column('degraded_conditions', sa.Boolean(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['corridor_id'], ['corridors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_weather_snapshots_corridor_recorded_at',
        'weather_snapshots',
        ['corridor_id', 'recorded_at'],
    )

    op.add_column(
        'risk_assessments',
        sa.Column('weather_snapshot_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_risk_assessments_weather_snapshot_id',
        'risk_assessments', 'weather_snapshots',
        ['weather_snapshot_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_risk_assessments_weather_snapshot_id', 'risk_assessments', type_='foreignkey')
    op.drop_column('risk_assessments', 'weather_snapshot_id')

    op.drop_index('ix_weather_snapshots_corridor_recorded_at', table_name='weather_snapshots')
    op.drop_table('weather_snapshots')
