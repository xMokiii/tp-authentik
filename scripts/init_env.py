#!/usr/bin/env python3
"""Generate local secrets once, without printing or overwriting them."""
from pathlib import Path
import os
import secrets
import sys


def initialize(root):
    root = Path(root)
    destination = root / ".env"
    values = {
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "AUTHENTIK_SECRET_KEY": secrets.token_hex(32),
        "GRAFANA_ADMIN_PASSWORD": secrets.token_hex(24),
    }
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("REFUS : .env existe deja. Aucun secret n'a ete modifie.", file=sys.stderr)
        return 1
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write("# Secrets locaux : ne pas versionner ni transmettre.\n")
        for key, value in values.items():
            stream.write(f"{key}={value}\n")
    for name in ("data/authentik/media", "custom-templates", "certs", "docs", "captures", "backups"):
        (root / name).mkdir(parents=True, exist_ok=True)
    print(".env cree ; secrets non affiches. Dossiers de travail prepares.")
    return 0


if __name__ == "__main__":
    sys.exit(initialize(Path(__file__).resolve().parents[1]))
