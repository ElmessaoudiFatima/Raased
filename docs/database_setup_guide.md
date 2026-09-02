# Raased — Guide d'installation de la base de données 

Ce guide t'accompagne de zéro jusqu'à avoir toutes les tables de Raased créées
dans ta base PostgreSQL locale, via SQLAlchemy + Alembic.

---

## 1. Installer PostgreSQL + PostGIS

### Si tu n'as pas encore PostgreSQL

1. Télécharge l'installeur Windows ici : https://www.postgresql.org/download/windows/
2. Lance l'installeur, garde les options par défaut, retiens le **mot de passe** que tu donnes à l'utilisateur `postgres`.
3. À la fin de l'installation, l'assistant propose de lancer **Stack Builder** — accepte.
4. Dans Stack Builder, sélectionne ta version de PostgreSQL → catégorie **Spatial Extensions** → coche **PostGIS**. Installe-le.

### Si tu as déjà PostgreSQL mais pas PostGIS

Relance **Stack Builder** seul (cherche "Stack Builder" dans le menu Démarrer), sélectionne ta version de PostgreSQL installée, puis suis l'étape 4 ci-dessus.

### Vérifie l'installation

Ouvre une invite de commande :
```powershell
psql --version
```
Si la commande n'est pas reconnue, ajoute le dossier `bin` de PostgreSQL (ex: `C:\Program Files\PostgreSQL\16\bin`) à ta variable d'environnement `PATH`, puis relance ton terminal.

---

## 2. Créer la base de données et l'utilisateur du projet

Connecte-toi à PostgreSQL via pgAdmin
(il te demande le mot de passe défini à l'installation)

Une fois connecter, exécute :
```sql
CREATE USER raased WITH PASSWORD 'raased';
```
Ensuite : 

```sql
CREATE DATABASE raased OWNER raased;
```
Et finalemnt active l'extension PostGIS ,exécute ça dans la base de données raased :
```sql
CREATE EXTENSION postgis;
```
> Adapte `raased`/`raased` (nom d'utilisateur/mot de passe) si tu préfères autre chose —
> dans ce cas, garde bien la cohérence avec l'étape 5 (fichier `.env`).

## 3. Se placer dans le backend

```powershell
cd backend
```
---

## 4. Créer l'environnement virtuel Python et installer les dépendances

```powershell
python -m venv .venv
```

Active-le :
```powershell
.venv\Scripts\activate
```

Installe les dépendances :
```powershell
pip install -r requirements.txt
```

---

## 5. Configurer le fichier `.env`

Copie le modèle :
```powershell
copy .env.example .env
```

Ouvre `.env` et vérifie/adapte cette ligne pour qu'elle corresponde à ton utilisateur/mot de passe/nom de base créés à l'étape 2 :
```
DATABASE_URL=postgresql+asyncpg://raased:raased@localhost:5432/raased
```

### Teste que la config se charge correctement

```powershell
python -c "from app.core.config import get_settings; print(get_settings().DATABASE_URL)"
```
Ça doit afficher ton URL sans erreur d'import.

---

## 6. Vérifier que la version de SQLAlchemy est compatible avec ta version de Python

Si tu es sous **Python 3.13**, il faut SQLAlchemy ≥ 2.0.36 (une version antérieure plante avec les modèles qui utilisent des `relationship()`) :
```powershell
pip install --upgrade "sqlalchemy>=2.0.36,<2.1.0"
```

---

## 7. Configurer Alembic (déjà fait dans le repo — à vérifier seulement)

Le dossier `migrations/` doit déjà exister dans le repo, avec `migrations/env.py` déjà configuré pour :
- importer `Base` depuis `app.db.base`
- importer tous les modèles depuis `app.db.models` (pour qu'Alembic les détecte)
- utiliser l'URL de `.env`, avec le driver `psycopg2` (sync) au lieu de `asyncpg` (async)

Si jamais `migrations/` n'existe pas encore chez toi (nouveau clone sans ce dossier committé), lance :
```powershell
alembic init migrations
```
puis demande à moi (fatima) le contenu à jour de `env.py`.

---

## 8. Générer et appliquer les migrations

### Générer le fichier de migration (uniquement si tu modifies un modèle, ou pour la toute première fois si `migrations/versions/` est vide)

```powershell
alembic revision --autogenerate -m "initial schema"
```

### ⚠️ Vérification manuelle obligatoire avant d'appliquer

Ouvre le fichier généré dans `migrations/versions/xxxxx_initial_schema.py` et vérifie/corrige ces deux points connus :

**a) Import manquant en haut du fichier** — ajoute si absent :
```python
import geoalchemy2
```

**b) Ne jamais toucher à `spatial_ref_sys`** (table système PostGIS) :
- Supprime la ligne `op.drop_table('spatial_ref_sys')` dans `upgrade()` si présente
- Supprime le bloc `op.create_table('spatial_ref_sys', ...)` dans `downgrade()` si présent

**c) Doublons d'index spatiaux** — GeoAlchemy2 crée automatiquement un index GiST dès qu'une colonne géométrique est créée. Si Alembic génère aussi des `op.create_index('idx_..._geometry', ...)` / `op.create_index('idx_..._location', ...)`, **supprime ces lignes en double** dans `upgrade()` ainsi que leurs `op.drop_index(...)` correspondants dans `downgrade()` — sinon tu auras une erreur `DuplicateTable`.

### Appliquer la migration

```powershell
alembic upgrade head
```

---

## 9. Vérifier que tout est bien créé

```powershell
psql -U raased -d raased -c "\dt"
```

Tu dois voir la liste de toutes les tables du projet, plus `alembic_version` (table de suivi Alembic) et `spatial_ref_sys` (table système PostGIS, propriétaire `postgres`).

---

## Pour la suite : à chaque modification d'un modèle

1. Modifie le fichier dans `app/db/models/`
2. Génère une nouvelle migration :
   ```powershell
   alembic revision --autogenerate -m "description du changement"
   ```
3. **Relis toujours le fichier généré** (points a/b/c de l'étape 8)
4. Applique :
   ```powershell
   alembic upgrade head
   ```
5. Commit et push le fichier de migration généré (`migrations/versions/...py`) — c'est ce fichier que le reste de l'équipe va exécuter avec `alembic upgrade head` pour rester synchronisé.

---