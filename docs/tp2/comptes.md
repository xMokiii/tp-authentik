# TP2 — Comptes et attributs

Les mots de passe ne figurent pas dans ce document. Ils ont été générés aléatoirement (16 caractères, un par compte) et sont conservés hors du dépôt.

## Identités créées (étape 2)

| Username | Nom affiché | Email | Type | Path | Actif |
|---|---|---|---|---|---|
| `alice` | Alice Martin | alice@nova-services.test | Internal | users | Oui |
| `bob` | Bob Dupont | bob@nova-services.test | Internal | users | Oui → **Non** (départ, étape 19) |
| `charlie` | Charlie Bernard | charlie@nova-services.test | Internal | users | Oui |
| `mfa-test` | Compte test MFA | mfa-test@nova-services.test | Internal | users | Oui → **Non** (après le test MFA) |

Les adresses `.test` sont fictives : aucun e-mail n'est envoyé.

## Attributs métier (étape 3)

| Utilisateur | Département | Attribut `role` | Niveau `clearance_level` |
|---|---|---|---|
| alice | RH | Manager RH | 2 |
| bob | Development | Backend Developer | 1 |
| charlie | IT | System Administrator | 5 |

Valeurs relues en base après l'enregistrement. `clearance_level` est stocké comme un **nombre** (`2`, et non `"2"`) :

```
alice   {'role': 'Manager RH', 'department': 'RH', 'clearance_level': 2}
bob     {'role': 'Backend Developer', 'department': 'Development', 'clearance_level': 1}
charlie {'role': 'System Administrator', 'department': 'IT', 'clearance_level': 5}
```

Ces attributs sont des **données métier** : ils ne donnent aucun droit. Pour les 3 comptes, `is_superuser = False`. Le seul groupe superutilisateur est `authentik Admins`, et il ne contient que `akadmin`.

### Mini-exercice — règle `department == IT` et `clearance_level >= 3`

1. **Seul `charlie`** satisfait les deux conditions (IT, niveau 5). Alice et Bob échouent dès la condition sur le département.
2. Un utilisateur qui pourrait modifier son propre niveau d'habilitation s'attribuerait lui-même des accès : on perdrait la séparation entre demandeur et approbateur, et l'escalade de privilèges serait triviale. Ces attributs doivent rester sous contrôle administratif, et ne jamais être exposés dans un formulaire de profil modifiable.
3. Non. Avec un niveau 2, la condition `clearance_level >= 3` devient fausse, donc toute la règle (un ET logique) devient fausse. L'accès doit être perdu dès la prochaine évaluation de la règle.

## Cycle de vie (étape 4)

| Situation | Opérations |
|---|---|
| Arrivée (Joiner) | Créer l'identité, vérifier ses informations, enrôler les authentificateurs, attribuer les accès approuvés |
| Mobilité (Mover) | Réévaluer les droits, retirer ceux de l'ancien poste, attribuer ceux du nouveau |
| Départ (Leaver) | Bloquer les nouvelles connexions, révoquer sessions et jetons, retirer les droits, traiter les comptes applicatifs |

**Suspension temporaire de Bob**, test réel (voir [tests.md](tests.md)) :
- Bob désactivé, puis connexion avec son bon mot de passe → **refusée**. Sa fiche et ses attributs existent toujours.
- Bob réactivé, puis nouvelle connexion → **acceptée**.

> **Question : pourquoi distinguer la fermeture du compte et celle de toutes ses sessions applicatives ?**
> Désactiver le compte dans l'IdP empêche seulement les *nouvelles* authentifications. Les applications comme Grafana ont créé leur propre session (cookie) après le SSO, et elle reste valide jusqu'à son expiration ou sa révocation. Il en va de même pour les jetons OAuth déjà émis. Le départ doit donc aussi traiter les sessions et les comptes dans chaque application. Cela a été vérifié à l'étape 19.

## Comptes créés par le bonus CSV (étape 24)

Ils ont été créés par `scripts/import_users.py` via l'API. Tous sont **inactifs**, sans groupe et sans mot de passe utilisable :

| Username | Département | Rôle | Niveau | Actif | Groupes |
|---|---|---|---|---|---|
| david | Development | Frontend Developer | 1 | Non | — |
| emma | RH | RH Assistant | 2 | Non | — |
| frank | IT | Technician | 3 | Non | — |
| grace | Finance | Accountant | 2 | Non | — |
| henry | Audit | Auditor | 4 | Non | — |

## État initial et état final

| Compte | Initial (après l'étape 6) | Final (fin de TP) | Groupe métier final | Accès Grafana final |
|---|---|---|---|---|
| alice | actif, RH | actif | RH | Viewer ; dossier RH en lecture seule |
| bob | actif, Dev | **inactif** | aucun groupe donnant accès | compte Grafana désactivé, sessions révoquées |
| charlie | actif, Admin | actif | Admin | Admin de l'organisation (pas GrafanaAdmin) |
| mfa-test | actif, sans groupe | **inactif** | aucun | aucun |
| akadmin | superutilisateur Authentik | inchangé, MFA enrôlé | authentik Admins | aucun (compte d'administration de l'IdP) |
