# TP2 — Tests : scénario, attendu, observé, preuve

Abréviations des preuves :
- **auto** : [`scripts/tp2_recette.py`](../../scripts/tp2_recette.py), qui rejoue de vrais parcours de connexion (flow Authentik puis OAuth Grafana) avec [`scripts/sso_check.py`](../../scripts/sso_check.py). Résultats bruts dans [`recette-auto.json`](recette-auto.json) : **20/20 conformes**.
- **ak** : relevé dans la base Authentik (`ak shell`) ou dans son journal d'événements.
- **nav** : test manuel dans une fenêtre privée du navigateur.

Les parcours scriptés ont été exécutés **avant** l'activation de la MFA obligatoire, car ils ne saisissent pas de code TOTP. Après l'activation, le parcours SSO complet avec MFA a été refait au navigateur (test 20).

## Tableau de recette du TP

| # | Test | Résultat attendu | Résultat observé | Preuve |
|---|---|---|---|---|
| 1 | Identités et attributs | 3 comptes conformes au scénario | alice, bob, charlie créés (Internal, path `users`), attributs relus en base, `clearance_level` numérique. Chacun se connecte au portail | ak, auto ; [comptes.md](comptes.md) |
| 2 | Suspension puis retour de Bob | Refus, puis connexion après réactivation | Désactivé : connexion **refusée**, fiche et attributs conservés. Réactivé : connexion **OK** | auto (`sso_check authentik bob`) |
| 3 | Groupes métier | RH, Dev et Admin attribués correctement | Admin = [charlie], Dev = [bob], RH = [alice], Audit = []. Aucun groupe superutilisateur (sauf `authentik Admins`) | ak ; capture `authentik-groupe-admin.png` |
| 4 | Compte sans facteur après obligation MFA | Refus | `mfa-test` : **refusé** après le mot de passe (« No (allowed) MFA authenticator configured »), puis désactivé | auto |
| 5 | Charlie avec TOTP valide | Succès | **OK**. Événement `login` avec `mfa_devices = [totpdevice]` | nav + ak |
| 6 | Charlie avec TOTP incorrect | Refus | **Refusé** à l'étape MFA (« Invalid Token ») | auto (code 000000) |
| 7 | Code de récupération utilisé deux fois | Succès, puis refus | 1re utilisation : **OK** (`login`, `staticdevice`, 6 → 5 codes). 2e utilisation du même code : **refusée** (`login_failed`) | nav + ak |
| 8 | Alice dans Grafana | Viewer | **Viewer**, isGrafanaAdmin = False | auto ; capture `grafana-roles-sso.png` |
| 9 | Bob dans Grafana | Editor avant départ | **Editor** | auto ; capture `grafana-roles-sso.png` |
| 10 | Charlie dans Grafana | Admin d'organisation, pas administrateur global | **Admin** de *Main Org.*, isGrafanaAdmin = **False** | auto ; capture `grafana-roles-sso.png` |
| 11 | Alice sans groupe autorisé | Refus lors d'une nouvelle connexion | Sans RH : **refusée par Authentik** sur `/application/o/authorize/` (bindings de l'application). RH rétabli : OK | auto |
| 12 | Mobilité de Bob vers Audit | Viewer après nouvelle connexion OAuth | Ancienne session : encore **Editor** (pas de réévaluation). Nouvelle connexion : **Viewer**, modification du tableau **refusée (403)**. Retour dans Dev : Editor | auto |
| 13 | Dossiers RH et Dev | Accès conforme, y compris par URL directe | Bob : Dev 200 en lecture et écriture, RH **403**. Alice : RH 200 en lecture, écriture **403**, Dev **403**. Charlie : 200 / 200. Testé par URL directe d'API | auto ; [rbac.md](rbac.md) |
| 14 | Bob désactivé dans l'IdP | Nouvelle authentification refusée | **Refusée** (« Mot de passe invalide » : Authentik ne révèle pas que le compte est désactivé) | auto + nav ; capture `bob-reconnexion-refusee.png` |
| 15 | Deprovisioning complet de Bob | Ancienne session et nouvel accès refusés | Ancienne session : **refusée** (« user token not found », retour au login). Nouvel accès : **refusé** | nav + journaux Grafana |

## Tests complémentaires

| # | Test | Attendu | Observé | Preuve |
|---|---|---|---|---|
| 16 | Test de référence avant MFA (Alice) | Le mot de passe suffit (Skip, aucun appareil) | Connexion OK sans second facteur | auto |
| 17 | Alice après obligation MFA | Second facteur demandé | Challenge `authenticator-validate` (classe `totp`) présenté après le mot de passe | auto |
| 18 | Administrateur avec mot de passe + second facteur | Connexion acceptée | **OK** | nav |
| 19 | Charlie n'administre pas l'IdP | Pas de droits superutilisateur | `is_superuser = False` | ak |
| 20 | SSO Grafana de Charlie **avec MFA** | Retour dans Grafana, rôle Admin | `login` avec TOTP à 11:58:16, `authorize_application` Grafana à 11:58:58, rôle Admin | nav + ak ; capture `grafana-roles-sso.png` |
| 21 | Tableau « Nova Services — Démonstration IAM » | Charlie crée ; Alice lit sans enregistrer ; Bob modifie | Création 200 ; Alice lecture 200 / écriture **403** ; Bob écriture 200 ; `updatedBy = bob` vu par Charlie | auto |
| 22 | Découverte OIDC | Endpoints publiés | issuer `http://localhost:9000/application/o/grafana/`, `authorize`, `token`, `userinfo`, `jwks`. Scopes : `nova_groups`, `openid`, `email`, `profile` | curl |
| 23 | Étape 20 : SSO uniquement | Formulaire local masqué, Basic Auth coupée | `disableLoginForm: true`. Bouton Authentik présent. Basic Auth `admin` : **HTTP 401**. POST `/login` local : **HTTP 400** | curl |
| 24 | Bonus CSV | 5 comptes inactifs ; relance sans modification | 5 « Créé inactif » ; relance : 5 « Déjà présent, inchangé ». Inactifs, sans groupe, sans mot de passe utilisable. Jeton API révoqué | script + ak |

## Étape 19 : départ de Bob, chronologie observée

| Moment | Action | Observation |
|---|---|---|
| T0 | Bob connecté à Grafana par SSO + TOTP (fenêtre séparée) | Accès au tableau « Tableau Dev » |
| T1 | **Désactivation de Bob dans Authentik** | 9 sessions Authentik avant la désactivation, 0 après (Authentik les supprime). 10 sessions Grafana toujours actives |
| T2 | Nouvelle connexion Authentik de Bob | **Refusée** |
| T3 | Actualisation de l'ancienne session Grafana | **Toujours connecté** : Bob ouvre « Tableau Dev », le modifie et voit « **Dashboard saved** » ← l'IdP seul ne coupe pas la session applicative |
| T4 | Retrait dans Authentik | Groupe `Dev` retiré. Jetons OAuth (access, refresh, codes) : 0 restant |
| T5 | Retrait dans Grafana (compte local admin) | « Disable user » **refusé** par Grafana (« Could not disable external user », compte issu d'OAuth). Mesure de remplacement : **retrait de l'organisation**. Sessions **révoquées** (0 restante). Retrait de l'équipe `nova-dev`. Aucune permission directe |
| T6 | Actualisation de l'ancienne session | **Refusée** : « user token not found » dans les journaux, retour à la page de connexion |
| T7 | Nouvelle connexion SSO de Bob | **Refusée** par Authentik |

**Conclusion :** désactiver le compte dans l'IdP bloque les *nouvelles* authentifications, mais **pas** la session Grafana déjà ouverte : Bob a encore pu enregistrer une modification après sa désactivation. Le départ n'est effectif qu'après avoir traité aussi l'application (sessions, appartenance, équipes).

## Captures

| Fichier | Contenu |
|---|---|
| `captures/authentik-utilisateurs.png` | Liste des utilisateurs Authentik |
| `captures/authentik-groupe-admin.png` | Appartenances (groupe Admin) |
| `captures/mfa-akadmin-totp-static.png`, `captures/mfa-charlie-totp-static.png` | Périphériques MFA (TOTP + Static) |
| `captures/grafana-roles-sso.png` | Rôles Grafana après SSO |
| `captures/bob-session-apres-desactivation-idp.png`, `captures/bob-sauvegarde-apres-desactivation-idp.png` | Session de Bob encore active après la désactivation dans l'IdP |
| `captures/bob-reconnexion-refusee.png` | Refus d'accès |
