"""Explicit local operations; never creates a default account or exposes a public bootstrap."""

import argparse
import getpass
import json
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models import Auditoria, Rol, Usuario
from app.retention import purge_expired
from app.security import credential_digest


def bootstrap_admin(name: str, credential: str) -> int:
    name, credential = name.strip(), credential.strip()
    if not name or len(name) > 150 or not credential or len(credential) > 256:
        raise ValueError("A valid name and registered credential are required")
    with Session(engine) as db, db.begin():
        # Makes two concurrent local bootstrap commands mutually exclusive.
        db.execute(text("SELECT pg_advisory_xact_lock(848374672)"))
        role = db.scalar(select(Rol).where(Rol.nombre == "administrador"))
        if role is None:
            raise ValueError("Apply migrations first")
        exists = db.scalar(select(Usuario.id).where(Usuario.rol_id == role.id))
        if exists is not None:
            raise ValueError("An administrator already exists; use the administration API")
        user = Usuario(
            nombre=name, rol=role, activo=True, credencial_uid=credential_digest(credential)
        )
        db.add(user)
        db.flush()
        db.add(
            Auditoria(
                usuario_id=user.id,
                accion="bootstrap_administrador",
                entidad="usuario",
                entidad_id=str(user.id),
                creado_at=datetime.now(UTC),
            )
        )
        return user.id


def main():
    parser = argparse.ArgumentParser(description="Thesora local administrative operations")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap-admin")
    bootstrap.add_argument("--nombre", required=True)
    retention = commands.add_parser("retention")
    retention.add_argument(
        "--execute",
        action="store_true",
        help="Delete expired records; the default only previews counts",
    )
    args = parser.parse_args()
    try:
        if args.command == "bootstrap-admin":
            identity = bootstrap_admin(args.nombre, getpass.getpass("Credencial registrada: "))
            print(json.dumps({"administrador_id": identity}))
        else:
            print(json.dumps(purge_expired(dry_run=not args.execute)))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
