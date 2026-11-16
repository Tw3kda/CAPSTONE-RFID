"""Add nullable password hashes; legacy accounts receive no invented password.

Revision ID: c8d7e6f5a432
Revises: b7c9d4e2a610
"""

import sqlalchemy as sa
from alembic import op

revision = "c8d7e6f5a432"
down_revision = "b7c9d4e2a610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuario", sa.Column("clave_hash", sa.Text(), nullable=True))


def downgrade():
    # Reverting intentionally removes ID-login passwords, not accounts or history.
    op.drop_column("usuario", "clave_hash")
