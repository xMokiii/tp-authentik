# TP2 — Procédures de récupération

Ce document ne contient aucun secret : ni mot de passe, ni code de récupération, ni QR code, ni Client Secret.

## 1. État du flow de connexion relevé avant la modification MFA (étape 7)

Flow utilisé par la Brand `authentik-default` : `default-authentication-flow`.

| Ordre | Stage | Type | Policy sur le binding |
|---|---|---|---|
| 10 | default-authentication-identification | Identification | — |
| 20 | default-authentication-password | Password | `default-authentication-flow-password-stage` : saute le mot de passe seulement si l'utilisateur est déjà authentifié par un autre backend |
| 30 | default-authentication-mfa-validation | Authenticator Validation | `default-authentication-flow-authenticator-validate-stage` : saute la MFA seulement en connexion *passwordless* WebAuthn (non utilisée ici) |
| 100 | default-authentication-login | User Login | — |

Aucune policy ne fait sauter le contrôle MFA pour une connexion par mot de passe. L'ordre est correct : la MFA (30) passe avant la création de session (100).

| Paramètre de `default-authentication-mfa-validation` | Avant (installation neuve) | Après (étape 10) |
|---|---|---|
| Device classes | static, totp, webauthn, duo, sms, email | **TOTP, Static** |
| Not configured action | **Skip** | **Deny** |
| Last validation threshold | seconds=0 | seconds=0 |

Pour revenir en arrière en cas d'erreur, il suffit de remettre ces valeurs depuis la session administrateur conservée ouverte pendant les essais.

## 2. Perte du second facteur (téléphone TOTP perdu ou volé)

Préalables : l'administrateur (`akadmin`) et Charlie possèdent des codes de récupération (authentificateur **Static**), rangés dans un coffre séparé du téléphone. Chaque code ne sert qu'une fois. Le test « même code utilisé deux fois → refus » est documenté dans [tests.md](tests.md).

**Si l'utilisateur a encore un code de récupération :**
1. Il se connecte avec son mot de passe, choisit la méthode Static et saisit un code.
2. Dans *Paramètres → Authentificateurs*, il supprime l'appareil TOTP perdu.
3. Il enrôle le nouveau téléphone (TOTP) et vérifie une nouvelle connexion.
4. Il régénère ses codes de récupération, car les anciens ont été entamés et peuvent avoir été exposés.

**Si l'utilisateur n'a plus aucun facteur (support administrateur) :**
1. **Vérifier l'identité** du demandeur selon la procédure de support : rappel sur un numéro connu, validation par le manager, présence physique. Jamais sur la seule foi d'un e-mail ou d'un appel entrant.
2. **Révoquer** l'appareil perdu : *Admin → Répertoire → Utilisateurs → fiche → Authentificateurs*, supprimer l'appareil.
3. Examiner les **événements** (connexions, échecs MFA) et les **sessions** de l'utilisateur. Révoquer les sessions douteuses dans Authentik (onglet Sessions) **et dans les applications** (Grafana : *Administration → Users → Sessions*).
4. Organiser une **récupération contrôlée**. Avec `Not configured action = Deny`, supprimer tous les appareils ne rend **pas** l'accès possible : l'utilisateur serait refusé. L'administrateur doit fournir un moyen d'enrôlement maîtrisé, par exemple un lien de récupération à usage unique remis en main propre, ou un enrôlement en sa présence. Il ne faut **pas** désactiver la MFA pour tout le monde.
5. L'utilisateur **enrôle** son nouvel appareil, puis on vérifie une nouvelle connexion complète.
6. **Renouveler** les codes de récupération si leur confidentialité est incertaine, et tracer l'intervention.

**Pourquoi protéger un code de récupération comme un secret d'authentification ?** Il **remplace** le second facteur. Quiconque connaît le mot de passe et un code valide se connecte sans le téléphone. Il ne doit donc pas être stocké avec le mot de passe, ni dans un fichier en clair, ni dans un ticket. Sa valeur est identique à celle du facteur qu'il remplace.

## 3. Secours Grafana en cas de panne de l'IdP (étape 20)

En fonctionnement normal, le formulaire local et Basic Auth sont désactivés (`GF_AUTH_DISABLE_LOGIN_FORM=true`, `GF_AUTH_BASIC_ENABLED=false`) et les utilisateurs passent par Authentik.

Le mot de passe du compte local `admin` de Grafana est conservé dans un coffre. Seul un administrateur de l'**hôte Docker** peut appliquer la procédure suivante :

1. Dans `docker-compose.yml`, service `grafana`, remettre temporairement :
   ```yaml
   GF_AUTH_DISABLE_LOGIN_FORM: "false"
   GF_AUTH_BASIC_ENABLED: "true"
   ```
2. Recréer le conteneur. Un simple `docker restart` ne relit pas le Compose.
   ```bash
   docker compose config --quiet
   docker compose up -d --no-deps --force-recreate grafana
   ```
3. Se connecter avec le compte local `admin`, intervenir, et tracer l'intervention.
4. **Rétablir** immédiatement `true` / `false`, puis recréer Grafana à nouveau.

Ce chemin contourne la MFA d'Authentik. Il ne doit jamais devenir un usage quotidien.

Masquer le formulaire ne supprime pas les comptes locaux, ne révoque pas les sessions existantes et ne révoque pas les jetons API.
