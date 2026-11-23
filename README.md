# Nova Services — Laboratoire IAM (Authentik, Grafana, Gitea)

Module : Gouvernance des identités & habilitations — 2026–2027

| TP | Sujet | Rendu |
|---|---|---|
| TP1 | Installer Authentik, Grafana et Gitea avec Docker | [docs/tp1/rendu.md](docs/tp1/rendu.md) |
| TP2 | Gestion des identités, RBAC, MFA, SSO et OIDC (Authentik ↔ Grafana) | [docs/tp2/rendu.md](docs/tp2/rendu.md) |

## Contenu du dépôt

| Chemin | Rôle |
|---|---|
| [`docker-compose.yml`](docker-compose.yml) | 5 services (`postgres`, `authentik-server`, `authentik-worker`, `grafana`, `gitea`), réseau `iam-network`, volumes, healthchecks — projet `nova-iam` |
| [`.env.example`](.env.example) | Noms des variables, **sans secret** |
| [`scripts/init_env.py`](scripts/init_env.py) | Génère `.env` une seule fois (refuse d'écraser) |
| [`scripts/sso_check.py`](scripts/sso_check.py), [`scripts/tp2_recette.py`](scripts/tp2_recette.py) | TP2 — recette automatisée des parcours SSO, rôles et dossiers |
| [`scripts/import_users.py`](scripts/import_users.py), [`users.csv`](users.csv) | TP2 bonus — import CSV de comptes inactifs via l'API |
| [`docs/`](docs/) | Rendus et captures de chaque TP |

Le fichier `.env`, le dossier `secrets/`, les données (`data/`), les certificats, les sauvegardes et les captures brutes sont exclus par [`.gitignore`](.gitignore).

## Démarrage

```bash
python3 scripts/init_env.py          # une seule fois
docker compose config --quiet
docker compose pull
docker compose run --rm --no-deps --user 0 --entrypoint sh authentik-server \
  -c 'mkdir -p /data/media && chown -R 1000:1000 /data'
docker compose up -d --wait --wait-timeout 600
docker compose ps
```

| Service | URL |
|---|---|
| Authentik | http://localhost:9000/ (initialisation via la racine → `/setup`) |
| Grafana | http://localhost:3000 (connexion par Authentik uniquement depuis le TP2) |
| Gitea | http://localhost:3001 |

Pause : `docker compose stop` — Reprise : `docker compose up -d --wait --wait-timeout 600`.
Ne jamais utiliser `docker compose down -v` (efface les bases).
