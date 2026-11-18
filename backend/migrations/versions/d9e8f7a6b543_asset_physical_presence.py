"""Separate physical presence from loan/maintenance state; project existing observations.

Revision ID: d9e8f7a6b543
Revises: c8d7e6f5a432
"""

import sqlalchemy as sa
from alembic import op

revision = "d9e8f7a6b543"
down_revision = "c8d7e6f5a432"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activo", sa.Column("presente", sa.Boolean(), nullable=True))
    op.add_column(
        "activo", sa.Column("presencia_actualizada_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Use only known, current UID/location observations. No loan transitions or invented presence.
    op.execute(
        sa.text("""
        WITH latest AS (
            SELECT DISTINCT ON (e.activo_id) e.activo_id, e.ocurrido_at,
                (e.tipo <> 'RETIRADO' AND e.validacion = 'correcto') AS presente
            FROM evento e JOIN activo a ON a.id = e.activo_id
            JOIN lector l ON l.id = e.lector_id
            WHERE e.tipo IN ('RETIRADO', 'PRESENTE', 'DEVUELTO')
              AND e.uid_leido = a.rfid_uid
              AND e.validacion IN ('correcto', 'posicion_incorrecta')
              AND ((e.validacion = 'correcto' AND l.posicion_id = a.posicion_asignada_id)
                OR (e.validacion = 'posicion_incorrecta'
                    AND l.posicion_id <> a.posicion_asignada_id))
            ORDER BY e.activo_id, e.ocurrido_at DESC, e.recibido_at DESC,
                e.arranque DESC, e.secuencia DESC, e.id DESC
        )
        UPDATE activo a SET presente = latest.presente,
            presencia_actualizada_at = latest.ocurrido_at
        FROM latest WHERE a.id = latest.activo_id
    """)
    )


def downgrade():
    op.drop_column("activo", "presencia_actualizada_at")
    op.drop_column("activo", "presente")
