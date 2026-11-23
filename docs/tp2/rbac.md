# TP2 — Matrice RBAC

## Groupes Authentik (étape 6)

| Groupe | Superutilisateur | Parent | Membre(s) | Description (attribut) |
|---|---|---|---|---|
| Admin | Non | — | charlie | Administrateurs de l'organisation Grafana |
| Dev | Non | — | bob (retiré au départ) | Développeurs — rôle Grafana Editor |
| RH | Non | — | alice | Ressources humaines — rôle Grafana Viewer |
| Audit | Non | — | (vide) | Audit — rôle Grafana Viewer |

Un groupe nommé `Admin` n'a aucun pouvoir par lui-même : seules sa configuration (superutilisateur désactivé) et son utilisation par Grafana déterminent ses effets. Charlie, membre d'`Admin`, n'a **pas** accès à l'administration d'Authentik (`is_superuser = False`).

## Des groupes aux rôles Grafana

| Groupe Authentik | Claim `nova_groups` | Rôle Grafana | Portée réelle |
|---|---|---|---|
| Admin | `["Admin"]` | **Admin** (de l'organisation) | Administre l'organisation *Main Org.* : utilisateurs, équipes, dossiers, permissions. **Pas** GrafanaAdmin (administration du serveur) : `ALLOW_ASSIGN_GRAFANA_ADMIN=false` |
| Dev | `["Dev"]` | **Editor** | Crée et modifie les tableaux de bord *là où le rôle Editor a le droit d'écrire*. Ne limite **pas** au périmètre Dev |
| RH | `["RH"]` | **Viewer** | Consultation des tableaux autorisés |
| Audit | `["Audit"]` | **Viewer** | Consultation. Ne donne accès ni aux journaux Authentik ni à une fonction d'audit |
| aucun de ces groupes | `[]` | — | Refusé par Authentik (bindings de l'application), puis par Grafana (mode strict) |

Chaîne technique :
1. Le scope mapping `nova-grafana-groups` (scope `nova_groups`) ne publie que les appartenances directes à `Admin`, `Dev`, `RH` et `Audit`.
2. Le provider `nova-grafana-oidc` inclut les mappings `openid`, `profile`, `email` et `nova-grafana-groups`.
3. Grafana demande les scopes `openid profile email nova_groups`.
4. Grafana applique `GF_AUTH_GENERIC_OAUTH_ROLE_ATTRIBUTE_PATH`, évalué dans l'ordre Admin → Dev → RH/Audit, avec `ROLE_ATTRIBUTE_STRICT=true`.

**Double contrôle :**
- L'application Authentik `grafana` utilise le mode **ANY** et a 4 bindings de groupe (Admin, Dev, RH, Audit). Il suffit d'appartenir à l'un d'eux ; un utilisateur sans aucun de ces groupes est refusé avant même d'atteindre Grafana.
- Le mode strict de Grafana refuse toute identité qui arriverait sans rôle reconnu.

Le rôle est **réévalué à chaque nouvelle connexion OAuth** (`SKIP_ORG_ROLE_SYNC=false`). Changer un groupe dans Authentik n'affecte pas une session Grafana déjà ouverte.

## Permissions par dossier (étape 17)

Le rôle d'organisation ne cloisonne pas les départements. Le cloisonnement passe par les équipes et les dossiers Grafana, créés par Charlie :

| Équipe Grafana | Membres (gérés manuellement) |
|---|---|
| nova-dev | bob (retiré au départ) |
| nova-rh | alice |

| Dossier | Permissions configurées | Entrées générales Viewer / Editor |
|---|---|---|
| Dev | équipe `nova-dev` : **Edit** | retirées |
| RH | équipe `nova-rh` : **View** | retirées |

Le rôle Admin de l'organisation garde implicitement l'administration de tous les dossiers.

| Compte | Dossier Dev | Dossier RH | Vérifié aussi par URL directe |
|---|---|---|---|
| Bob (Editor, nova-dev) | lecture + modification (200 / 200) | **refusé (403)** | oui |
| Alice (Viewer, nova-rh) | **refusé (403)** | lecture seule (200, modification 403) | oui |
| Charlie (Admin) | administration (200) | administration (200) | oui |

La recherche « Tableau » ne renvoie que `Tableau RH` à Alice, et que `Tableau Dev` à Bob.

**Limites :**
- La synchronisation OIDC ne met **pas** à jour les équipes Grafana. Une mobilité ou un départ oblige à les modifier à la main (ou via l'API, ou une synchronisation d'équipes).
- Restreindre les dossiers n'isole pas les **données** : les droits sur les sources de données demandent une analyse séparée. Seuls des panneaux Text avec des données fictives ont été utilisés.
- Le tableau « Nova Services — Démonstration IAM » se trouve à la racine (General). Il garde les permissions par défaut (Editor : Edit, Viewer : View) et reste donc visible par tous les rôles.

## Mini-exercice — mobilité interne de Bob (étape 6)

Bob a été retiré de `Dev` puis ajouté à `Audit`, et on a vérifié les deux fiches de groupe. Il a ensuite été remis dans `Dev` et retiré d'`Audit`.

**Pourquoi garder les deux appartenances augmenterait ses privilèges :** les droits se cumulent. Avec `Dev` + `Audit`, l'expression de mapping trouve d'abord `Dev`, donc Bob resterait **Editor** alors que son nouveau poste ne demande que de la lecture. Une revue d'audit qui se croit en lecture seule pourrait ainsi modifier ce qu'elle audite, ce qui viole la séparation des tâches. C'est l'accumulation de droits (*privilege creep*) que la procédure Mover doit empêcher.
