#!/usr/bin/env python3
"""Recette TP2 : rejoue un parcours de connexion réel, comme un navigateur.

Usage :
  python scripts/sso_check.py authentik <user>     # connexion au portail Authentik
  python scripts/sso_check.py grafana <user>       # SSO Grafana via OIDC, affiche le rôle obtenu

Le mot de passe est lu dans l'invite (saisie masquée), ou dans la variable
d'environnement SSO_PASSWORD. Un code TOTP / de secours éventuel est lu dans SSO_CODE
ou demandé si Authentik l'exige. Aucun secret, cookie ni jeton n'est affiché.
"""
import getpass
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

AUTHENTIK = "http://localhost:9000"
GRAFANA = "http://localhost:3000"


class Browser:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.opener.addheaders = [("User-Agent", "nova-tp2-recette/1.0")]

    def csrf(self):
        for c in self.jar:
            if c.name == "authentik_csrf":
                return c.value
        return ""

    def request(self, url, data=None):
        headers = {"Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
            if url.startswith(GRAFANA):
                headers["Origin"] = GRAFANA
            else:
                headers["X-authentik-CSRF"] = self.csrf()
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=20) as r:
                return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.geturl(), e.read().decode("utf-8", "replace")


def ask_secret(prompt, env):
    return os.environ.get(env) or getpass.getpass(prompt)


def run_flow(b, page_url, user):
    """Exécute un flow Authentik à partir de l'URL /if/flow/<slug>/?... ; retourne l'URL finale."""
    parsed = urllib.parse.urlparse(page_url)
    slug = parsed.path.rstrip("/").split("/")[-1]
    api = f"{AUTHENTIK}/api/v3/flows/executor/{slug}/?" + urllib.parse.urlencode({"query": parsed.query})
    status, _, body = b.request(api)
    for _ in range(15):
        ch = json.loads(body)
        comp = ch.get("component")
        if comp == "xak-flow-redirect":
            return "redirect", urllib.parse.urljoin(AUTHENTIK, ch["to"])
        if comp == "ak-stage-access-denied":
            return "denied", ch.get("error_message") or "Accès refusé"
        if comp == "ak-stage-flow-error" or ch.get("response_errors"):
            errs = ch.get("response_errors") or ch.get("error")
            return "error", json.dumps(errs, ensure_ascii=False)
        if comp == "ak-stage-identification":
            payload = {"component": comp, "uid_field": user}
            if ch.get("password_fields"):
                payload["password"] = ask_secret(f"Mot de passe de {user} : ", "SSO_PASSWORD")
        elif comp == "ak-stage-password":
            payload = {"component": comp, "password": ask_secret(f"Mot de passe de {user} : ", "SSO_PASSWORD")}
        elif comp == "ak-stage-authenticator-validate":
            classes = [c.get("device_class") for c in ch.get("device_challenges", [])]
            if not classes:
                return "denied", "MFA exigé mais aucun authentificateur configuré"
            print(f"  -> second facteur demandé (classes disponibles : {', '.join(classes)})")
            payload = {"component": comp, "code": ask_secret("Code TOTP ou code de secours : ", "SSO_CODE")}
        elif comp == "ak-stage-consent":
            print("  -> consentement demandé, accepté")
            payload = {"component": comp, "token": ch.get("token", "")}
        else:
            return "error", f"étape non gérée : {comp}"
        status, _, body = b.request(api, payload)
        if status >= 400 and not body.startswith("{"):
            return "error", f"HTTP {status}"
    return "error", "trop d'étapes"


def login_authentik(user):
    b = Browser()
    status, final, _ = b.request(f"{AUTHENTIK}/if/flow/default-authentication-flow/?next=%2F")
    outcome, info = run_flow(b, final, user)
    label = "OK (session ouverte)" if outcome == "redirect" else f"REFUS ({info})"
    print(f"Connexion Authentik de {user} : {label}")
    return 0 if outcome == "redirect" else 1


def grafana_session(user):
    """Parcours SSO complet ; renvoie le navigateur connecté à Grafana, ou None si refus."""
    b = Browser()
    status, url, _ = b.request(f"{GRAFANA}/login/generic_oauth")
    for _ in range(6):
        p = urllib.parse.urlparse(url)
        if not (p.netloc.endswith(":9000") and p.path.startswith("/if/flow/")):
            break
        outcome, info = run_flow(b, url, user)
        if outcome != "redirect":
            print(f"SSO Grafana de {user} : REFUS côté Authentik ({info})")
            return None
        status, url, _ = b.request(info)
    p = urllib.parse.urlparse(url)
    if p.netloc.endswith(":9000") and p.path.startswith("/application/o/authorize"):
        print(f"SSO Grafana de {user} : REFUS côté Authentik (accès à l'application refusé, page {p.path})")
        return None
    if not p.netloc.endswith(":3000"):
        print(f"SSO Grafana de {user} : arrêt inattendu sur {p.netloc}{p.path} (HTTP {status})")
        return None
    status, _, body = b.request(f"{GRAFANA}/api/user")
    if status != 200:
        print(f"SSO Grafana de {user} : REFUS côté Grafana (HTTP {status} sur /api/user, page {p.path})")
        return None
    me = json.loads(body)
    _, _, orgs = b.request(f"{GRAFANA}/api/user/orgs")
    roles = ", ".join(f"{o['name']}={o['role']}" for o in json.loads(orgs))
    print(f"SSO Grafana de {user} : OK — login={me['login']} rôle(s)={roles} "
          f"isGrafanaAdmin={me.get('isGrafanaAdmin')} authLabels={me.get('authLabels')}")
    return b


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("authentik", "grafana"):
        print(__doc__)
        sys.exit(2)
    if sys.argv[1] == "authentik":
        sys.exit(login_authentik(sys.argv[2]))
    sys.exit(0 if grafana_session(sys.argv[2]) else 1)
