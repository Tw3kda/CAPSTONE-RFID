"""Represent a registered institutional identifier independently from the QR.

Revision ID: b7c9d4e2a610
Revises: 8a1c2e3f4b50
"""

import sqlalchemy as sa
from alembic import op

revision = "b7c9d4e2a610"
down_revision = "8a1c2e3f4b50"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable for legacy rows only: preserve QR credentials and never invent IDs.
    # API and bootstrap require an institutional ID for every new account.
    op.add_column(
        "usuario", sa.Column("identificador_institucional_hash", sa.Text(), nullable=True)
    )
    op.create_unique_constraint(
        "uq_usuario_identificador_institucional", "usuario", ["identificador_institucional_hash"]
    )


def downgrade():
    # Reverting this feature intentionally removes the separately registered ID hashes.
    op.drop_constraint("uq_usuario_identificador_institucional", "usuario", type_="unique")
    op.drop_column("usuario", "identificador_institucional_hash")
