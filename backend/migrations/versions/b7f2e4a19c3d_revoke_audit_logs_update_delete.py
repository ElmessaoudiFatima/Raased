"""revoke update/delete privileges on audit_logs (append-only enforcement)

Revision ID: b7f2e4a19c3d
Revises: 66412594b3ec
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7f2e4a19c3d'
down_revision: Union[str, None] = '66412594b3ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Retire les privilèges UPDATE et DELETE sur audit_logs pour le rôle
    applicatif "raased", afin de garantir la propriété "append-only" du
    journal d'audit même en cas de bug applicatif (l'INSERT reste autorisé).

    Limite connue : "raased" est propriétaire de la table (owner), donc ce
    rôle conserve la capacité de se re-GRANT ces privilèges lui-même. Cette
    migration protège contre les écritures accidentelles côté application,
    pas contre un accès direct malveillant avec les mêmes identifiants.
    """
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM raased;")


def downgrade() -> None:
    """Restaure les privilèges UPDATE et DELETE pour le rôle "raased"."""
    op.execute("GRANT UPDATE, DELETE ON audit_logs TO raased;")
