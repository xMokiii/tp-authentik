#!/usr/bin/env python3
import argparse
import csv
import getpass
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:9000"
FIELDS = {"username", "name", "email", "department", "role", "clearance_level"}


def read_users(filename):
    users = []
    seen = set()
    with open(filename, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != FIELDS:
            raise ValueError("En-têtes CSV incorrects")
        for number, row in enumerate(reader, start=2):
            if None in row or any(not (row.get(key) or "").strip() for key in FIELDS):
                raise ValueError(f"Ligne {number} : champ absent ou colonne en trop")
            row = {key: value.strip() for key, value in row.items()}
            username = row["username"]
            if username in seen:
                raise ValueError(f"Ligne {number} : username dupliqué")
            if not row["email"].endswith("@nova-services.test"):
                raise ValueError(f"Ligne {number} : adresse hors du domaine de TP")
            level = int(row["clearance_level"])
            if not 1 <= level <= 5:
                raise ValueError(f"Ligne {number} : niveau attendu entre 1 et 5")
            seen.add(username)
            users.append({
                "username": username,
                "name": row["name"],
                "email": row["email"],
                "is_active": False,
                "path": "users",
                "attributes": {
                    "department": row["department"],
                    "role": row["role"],
                    "clearance_level": level,
                },
            })
    return users


def api(token, path, payload=None):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = Request(BASE_URL + path, data=data, headers=headers)
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    users = read_users(args.csv_file)
    print(f"{len(users)} comptes validés ; création inactive sans groupe.")
    if not args.apply:
        for user in users:
            print("À créer :", user["username"])
        print("Simulation uniquement. Ajouter --apply pour appeler l'API.")
        return
    token = getpass.getpass("Jeton API Authentik (saisie masquée) : ").strip()
    if not token:
        raise ValueError("Jeton vide")
    for user in users:
        query = urlencode({"username": user["username"]})
        existing = api(token, "/api/v3/core/users/?" + query)
        if existing.get("results"):
            print("Déjà présent, inchangé :", user["username"])
            continue
        created = api(token, "/api/v3/core/users/", user)
        print("Créé inactif :", created["username"])


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        print(f"API : erreur HTTP {error.code}. Import interrompu.", file=sys.stderr)
        sys.exit(1)
    except (ValueError, OSError, URLError) as error:
        print(f"Import interrompu : {error}", file=sys.stderr)
        sys.exit(1)
