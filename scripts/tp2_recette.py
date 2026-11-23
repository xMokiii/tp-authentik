#!/usr/bin/env python3
"""Recette automatisée TP2 (étapes 16 et 17) : rôles Grafana, mobilité, refus, dossiers.

Rejoue de vrais parcours SSO (sso_check.py) et modifie les appartenances Authentik via
`docker compose exec authentik-server ak shell`. Les mots de passe des comptes de test sont
lus dans secrets/tp2-comptes.txt (fichier local ignoré par Git) ; rien de secret n'est affiché.

À lancer avant l'obligation MFA (les parcours scriptés ne saisissent pas de code TOTP).
"""
import base64
import json
import os
import subprocess
import time
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sso_check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
G = sso_check.GRAFANA
RESULTS = []


def secret_file():
    return dict(l.strip().split(": ", 1) for l in (ROOT / "secrets/tp2-comptes.txt").read_text().splitlines()
                if l.strip() and not l.startswith("#"))


PW = secret_file()


def env_value(key):
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise KeyError(key)


def ak(code):
    """Exécute du Python dans le shell Authentik (gestion des appartenances)."""
    subprocess.run(["docker", "compose", "exec", "-T", "authentik-server", "ak", "shell"], input=code,
                   text=True, cwd=ROOT, capture_output=True, check=True)


def set_groups(user, add=(), remove=()):
    ak("from authentik.core.models import User, Group\n"
       f"u = User.objects.get(username={user!r})\n"
       f"for g in {list(add)!r}: u.groups.add(Group.objects.get(name=g))\n"
       f"for g in {list(remove)!r}: u.groups.remove(Group.objects.get(name=g))\n")
    print(f"   [Authentik] {user} : +{list(add)} -{list(remove)}")


def login(user):
    os.environ["SSO_PASSWORD"] = PW[user]
    try:
        return sso_check.grafana_session(user)
    finally:
        os.environ.pop("SSO_PASSWORD", None)


def call(b, method, path, data=None):
    """Appel API Grafana avec la session du navigateur b, ou en admin local si b est None."""
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(G + path, data=body, method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "Origin": G})
    if b is None:
        cred = base64.b64encode(f"admin:{env_value('GRAFANA_ADMIN_PASSWORD')}".encode()).decode()
        req.add_header("Authorization", "Basic " + cred)
        opener = urllib.request.build_opener()
    else:
        opener = b.opener
    try:
        with opener.open(req, timeout=20) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {}


def check(name, expected, observed, ok):
    RESULTS.append((name, expected, observed, ok))
    print(f"   {'OK ' if ok else 'KO '} {name} — attendu : {expected} — observé : {observed}")


def role_of(login_name):
    _, users = call(None, "GET", "/api/org/users")
    for u in users:
        if u["login"] == login_name:
            _, full = call(None, "GET", f"/api/users/{u['userId']}")
            return u["role"], full.get("isGrafanaAdmin"), u["userId"]
    return None, None, None


def text_dashboard(title, text, folder_uid=None, uid=None, version=None):
    dash = {"title": title, "uid": uid, "schemaVersion": 39, "panels": [{
        "type": "text", "title": "Nova Services", "gridPos": {"h": 6, "w": 24, "x": 0, "y": 0},
        "options": {"mode": "markdown", "content": text}}]}
    if version is not None:
        dash["version"] = version
    payload = {"dashboard": dash, "overwrite": False, "message": "TP2"}
    if folder_uid:
        payload["folderUid"] = folder_uid
    return payload


def save_text(b, uid, new_text):
    st, d = call(b, "GET", f"/api/dashboards/uid/{uid}")
    if st != 200:
        return st
    dash = d["dashboard"]
    dash["panels"][0]["options"]["content"] = new_text
    payload = {"dashboard": dash, "overwrite": False, "message": "modification de test"}
    if d["meta"].get("folderUid"):
        payload["folderUid"] = d["meta"]["folderUid"]
    st, _ = call(b, "POST", "/api/dashboards/db", payload)
    return st


def main():
    print("== Étape 16 — SSO et rôles")
    charlie, alice, bob = login("charlie"), login("alice"), login("bob")
    for user, exp in (("alice", "Viewer"), ("bob", "Editor"), ("charlie", "Admin")):
        role, gadmin, _ = role_of(user)
        check(f"{user} dans Grafana", f"{exp}, pas GrafanaAdmin", f"{role}, GrafanaAdmin={gadmin}",
              role == exp and not gadmin)

    print("== Test fonctionnel : tableau de bord de démonstration")
    uid = "nova-demo-iam"
    st, _ = call(None, "GET", f"/api/dashboards/uid/{uid}")
    if st == 200:
        call(None, "DELETE", f"/api/dashboards/uid/{uid}")
    st, _ = call(charlie, "POST", "/api/dashboards/db",
                 text_dashboard("Nova Services — Démonstration IAM", "Tableau de bord du laboratoire Nova Services",
                                uid=uid))
    check("Charlie crée « Nova Services — Démonstration IAM »", "200", st, st == 200)
    time.sleep(3)  # les permissions gérées du nouveau tableau sont appliquées de façon asynchrone
    st, _ = call(alice, "GET", f"/api/dashboards/uid/{uid}")
    check("Alice consulte le tableau", "200", st, st == 200)
    st = save_text(alice, uid, "Tentative d'Alice")
    check("Alice enregistre une modification", "403 (refus)", st, st == 403)
    st = save_text(bob, uid, "Tableau de bord du laboratoire Nova Services — modifié par Bob")
    check("Bob enregistre une modification", "200", st, st == 200)
    _, d = call(charlie, "GET", f"/api/dashboards/uid/{uid}")
    by = d.get("meta", {}).get("updatedBy")
    check("Charlie voit la modification de Bob", "updatedBy=bob", f"updatedBy={by}", by == "bob")

    print("== Retrait d'un rôle : Bob Dev → Audit")
    set_groups("bob", add=["Audit"], remove=["Dev"])
    st, _ = call(bob, "GET", "/api/user")
    role_old, _, _ = role_of("bob")
    print(f"   (ancienne session Bob toujours valide : HTTP {st}, rôle encore {role_old} avant reconnexion)")
    bob = login("bob")
    role, _, _ = role_of("bob")
    check("Mobilité de Bob vers Audit", "Viewer après nouvelle connexion OAuth", role, role == "Viewer")
    st = save_text(bob, uid, "Tentative de Bob en Audit")
    check("Bob (Audit) modifie le tableau", "403 (refus)", st, st == 403)
    set_groups("bob", add=["Dev"], remove=["Audit"])
    bob = login("bob")
    role, _, _ = role_of("bob")
    check("Bob rétabli dans Dev", "Editor", role, role == "Editor")

    print("== Utilisateur sans groupe autorisé : Alice sans RH")
    set_groups("alice", remove=["RH"])
    b = login("alice")
    check("Alice sans groupe autorisé", "refus par Authentik", "connexion acceptée" if b else "refus",
          b is None)
    set_groups("alice", add=["RH"])
    alice = login("alice")
    check("Alice rétablie dans RH", "connexion OK", "OK" if alice else "refus", alice is not None)

    print("== Étape 17 — équipes et dossiers (avec la session de Charlie)")
    teams = {}
    for name, member in (("nova-dev", "bob"), ("nova-rh", "alice")):
        st, r = call(charlie, "POST", "/api/teams", {"name": name})
        if st != 200:
            _, s = call(charlie, "GET", f"/api/teams/search?name={name}")
            tid = s["teams"][0]["id"]
        else:
            tid = r["teamId"]
        _, _, uid_member = role_of(member)
        call(charlie, "POST", f"/api/teams/{tid}/members", {"userId": uid_member})
        # Grafana ajoute le créateur (Charlie) à l'équipe : on le retire, son rôle Admin suffit.
        _, _, uid_charlie = role_of("charlie")
        call(None, "DELETE", f"/api/teams/{tid}/members/{uid_charlie}")
        _, members = call(charlie, "GET", f"/api/teams/{tid}/members")
        teams[name] = tid
        print(f"   équipe {name} (id {tid}) : {[m['login'] for m in members]}")
    folders = {}
    for title, team, perm in (("Dev", "nova-dev", 2), ("RH", "nova-rh", 1)):
        fuid = f"nova-{title.lower()}"
        st, _ = call(charlie, "POST", "/api/folders", {"uid": fuid, "title": title})
        st, _ = call(charlie, "POST", f"/api/folders/{fuid}/permissions",
                     {"items": [{"teamId": teams[team], "permission": perm}]})
        _, acl = call(charlie, "GET", f"/api/folders/{fuid}/permissions")
        lisible = [(a.get("team") or a.get("role") or a.get("userLogin"), a["permissionName"]) for a in acl]
        print(f"   dossier {title} : permissions = {lisible}")
        duid = f"nova-dash-{title.lower()}"
        call(charlie, "POST", "/api/dashboards/db",
             {**text_dashboard(f"Tableau {title}", f"Données fictives — dossier {title}", uid=duid),
              "folderUid": fuid, "overwrite": True})
        folders[title] = duid

    time.sleep(3)

    def get(b, duid):
        return call(b, "GET", f"/api/dashboards/uid/{duid}")[0]

    check("Bob — dossier Dev (URL directe)", "lecture 200", get(bob, folders["Dev"]), get(bob, folders["Dev"]) == 200)
    st = save_text(bob, folders["Dev"], "Modifié par Bob dans Dev")
    check("Bob — modification dans Dev", "200", st, st == 200)
    check("Bob — dossier RH (URL directe)", "refus 403", get(bob, folders["RH"]), get(bob, folders["RH"]) == 403)
    check("Alice — dossier RH (URL directe)", "lecture 200", get(alice, folders["RH"]),
          get(alice, folders["RH"]) == 200)
    st = save_text(alice, folders["RH"], "Tentative d'Alice")
    check("Alice — modification dans RH", "refus 403", st, st == 403)
    check("Alice — dossier Dev (URL directe)", "refus 403", get(alice, folders["Dev"]),
          get(alice, folders["Dev"]) == 403)
    check("Charlie — dossiers Dev et RH", "200 / 200",
          f"{get(charlie, folders['Dev'])} / {get(charlie, folders['RH'])}",
          get(charlie, folders["Dev"]) == 200 and get(charlie, folders["RH"]) == 200)
    time.sleep(2)
    _, srch = call(alice, "GET", "/api/search?query=Tableau")
    print(f"   recherche « Tableau » vue par Alice : {[s['title'] for s in srch]}")
    _, srch = call(bob, "GET", "/api/search?query=Tableau")
    print(f"   recherche « Tableau » vue par Bob   : {[s['title'] for s in srch]}")

    (ROOT / "docs/tp2").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/tp2/recette-auto.json").write_text(json.dumps(
        [dict(test=n, attendu=e, observe=str(o), ok=k) for n, e, o, k in RESULTS], ensure_ascii=False, indent=2),
        encoding="utf-8")
    ko = [r for r in RESULTS if not r[3]]
    print(f"\n{len(RESULTS) - len(ko)}/{len(RESULTS)} contrôles conformes.")
    return 1 if ko else 0


if __name__ == "__main__":
    sys.exit(main())
