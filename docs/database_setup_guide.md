# Raased — Database Setup Guide

This guide walks you from zero to having all of Raased's tables created
in your local PostgreSQL database, via SQLAlchemy + Alembic.

---

## 1. Install PostgreSQL + PostGIS

### If you don't have PostgreSQL yet

1. Download the Windows installer here: https://www.postgresql.org/download/windows/
2. Run the installer, keep the default options, and remember the **password** you set for the `postgres` user.
3. At the end of the installation, the wizard offers to launch **Stack Builder** — accept.
4. In Stack Builder, select your PostgreSQL version → **Spatial Extensions** category → check **PostGIS**. Install it.

### If you already have PostgreSQL but not PostGIS

Relaunch **Stack Builder** on its own (search for "Stack Builder" in the Start menu), select your installed PostgreSQL version, then follow step 4 above.

### Verify the installation

Open a command prompt:
```powershell
psql --version
```
If the command isn't recognized, add the PostgreSQL `bin` folder (e.g. `C:\Program Files\PostgreSQL\16\bin`) to your `PATH` environment variable, then restart your terminal.

---

## 2. Create the database and the project user

Connect to PostgreSQL via pgAdmin
(it will ask for the password set during installation)

Once connected, run:
```sql
CREATE USER raased WITH PASSWORD 'raased';
```
Then:

```sql
CREATE DATABASE raased OWNER raased;
```
And finally, enable the PostGIS extension by running this inside the `raased` database:
```sql
CREATE EXTENSION postgis;
```
> Adapt `raased`/`raased` (username/password) if you prefer something else —
> in that case, keep it consistent with step 5 (the `.env` file).

## 3. Move into the backend folder

```powershell
cd backend
```
---

## 4. Create the Python virtual environment and install dependencies

```powershell
python -m venv .venv
```

Activate it:
```powershell
.venv\Scripts\activate
```

Install the dependencies:
```powershell
pip install -r requirements.txt
```

---

## 5. Configure the `.env` file

Copy the template:
```powershell
copy .env.example .env
```

Open `.env` and check/adapt this line so it matches the user/password/database name you created in step 2:
```
DATABASE_URL=postgresql+asyncpg://raased:raased@localhost:5432/raased
```

### Test that the config loads correctly

```powershell
python -c "from app.core.config import get_settings; print(get_settings().DATABASE_URL)"
```
It should print your URL with no import errors.

---

## 6. Check that your SQLAlchemy version is compatible with your Python version

If you're on **Python 3.13**, you need SQLAlchemy ≥ 2.0.36 (an earlier version crashes with models that use `relationship()`):
```powershell
pip install --upgrade "sqlalchemy>=2.0.36,<2.1.0"
```

---

## 7. Configure Alembic (already done in the repo — just verify)

The `migrations/` folder should already exist in the repo, with `migrations/env.py` already configured to:
- import `Base` from `app.db.base`
- import all models from `app.db.models` (so Alembic can detect them)
- use the URL from `.env`, with the `psycopg2` driver (sync) instead of `asyncpg` (async)

If `migrations/` doesn't exist yet on your machine (new clone without this folder committed), run:
```powershell
alembic init migrations
```
then ask me (fatima) for the up-to-date content of `env.py`.

---

## 8. Generate and apply migrations

### Generate the migration file (only if you modify a model, or for the very first time if `migrations/versions/` is empty)

```powershell
alembic revision --autogenerate -m "initial schema"
```

### ⚠️ Manual check required before applying

Open the generated file at `migrations/versions/xxxxx_initial_schema.py` and check/fix these two known points:

**a) Missing import at the top of the file** — add it if missing:
```python
import geoalchemy2
```

**b) Never touch `spatial_ref_sys`** (PostGIS system table):
- Remove the `op.drop_table('spatial_ref_sys')` line in `upgrade()` if present
- Remove the `op.create_table('spatial_ref_sys', ...)` block in `downgrade()` if present

**c) Duplicate spatial indexes** — GeoAlchemy2 automatically creates a GiST index as soon as a geometry column is created. If Alembic also generates `op.create_index('idx_..._geometry', ...)` / `op.create_index('idx_..._location', ...)` lines, **remove these duplicate lines** in `upgrade()` along with their corresponding `op.drop_index(...)` lines in `downgrade()` — otherwise you'll get a `DuplicateTable` error.

### Apply the migration

```powershell
alembic upgrade head
```

---

## 9. Verify that everything was created properly

```powershell
psql -U raased -d raased -c "\dt"
```

You should see the list of all the project's tables, plus `alembic_version` (Alembic's tracking table) and `spatial_ref_sys` (PostGIS system table, owned by `postgres`).

---

## Going forward: every time you modify a model

1. Edit the file in `app/db/models/`
2. Generate a new migration:
   ```powershell
   alembic revision --autogenerate -m "description of the change"
   ```
3. **Always re-read the generated file** (points a/b/c from step 8)
4. Apply it:
   ```powershell
   alembic upgrade head
   ```
5. Commit and push the generated migration file (`migrations/versions/...py`) — this is the file the rest of the team will run with `alembic upgrade head` to stay in sync.

---
