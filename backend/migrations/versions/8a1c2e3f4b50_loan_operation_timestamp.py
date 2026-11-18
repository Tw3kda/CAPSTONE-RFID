"""Reject queued physical observations predating the current operation.

Revision ID: 8a1c2e3f4b50
Revises: cb6d18ca0bf9
"""

import sqlalchemy as sa
from alembic import op

revision = "8a1c2e3f4b50"
down_revision = "cb6d18ca0bf9"
branch_labels = None
depends_on = None


def upgrade():
    # Existing pending operations start a fresh confirmation window at migration time.
    op.add_column(
        "prestamo",
        sa.Column(
            "operacion_iniciada_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.alter_column("prestamo", "operacion_iniciada_at", server_default=None)


def downgrade():
    op.drop_column("prestamo", "operacion_iniciada_at")
