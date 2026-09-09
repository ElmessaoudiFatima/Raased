# Raased — Plateforme API (Flask)

Couche plateforme de la solution Raased. Elle fournit toute l'API consommée par le frontend Next.js :

- **Authentification** : login, inscription en 5 étapes (Entreprise → Responsable → Code → Mot de passe → Documents),
  mot de passe oublié (email → code → nouveau mot de passe), invitations chauffeurs/managers via lien sécurisé.
- **Admin Raased** : revue des demandes d'entreprises, approbation / rejet, consultation des documents.
- **Manager** : tableau de bord, création de chauffeurs, invitation d'autres managers, cargaisons, trackers, alertes.
- **Chauffeur** : trajet attribué, carte temps réel, historique, alertes.
- **Cartes** : positions simulées en temps réel des convoyeurs, corridors et zones à risque (pour Leaflet).

> Le backend historique FastAPI (`backend/`) reste dans le dépôt (moteur agent / CAMARA). Cette API Flask
> reprend le modèle de données du design (`docs/raased_database_design.md`) et fonctionne en base dédiée.

---

## 1. Installation

Requis : Python 3.10+, PostgreSQL (recommandé) ou SQLite (démo locale sans serveur).

```bash
cd flask_api
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # Linux / macOS
```

Éditez `.env` :

- **PostgreSQL** : `DATABASE_URL=postgresql+psycopg://raased:raased@localhost:5432/raased_platform`
  (créez la base au préalable : `CREATE DATABASE raased_platform;`)
- **SQLite** (démo rapide) : `DATABASE_URL=sqlite:///./raased_platform.db`
- **SMTP** : laissez vide pour le mode dev → les codes sont affichés dans la console Flask.
  Pour de vrais e-mails, renseignez `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`.

## 2. Lancer

```bash
python app.py
```

Au démarrage, la base de données est créée et remplie de **données de démonstration**
(uniquement si elle est vide) : admin, 3 entreprises, managers, chauffeurs, trackers,
cargaisons en transit, alertes, corridors et zones à risque.

Serveur : `http://localhost:5000`

## 3. Comptes de démonstration

| Rôle | Email | Mot de passe |
|---|---|---|
| Admin Raased | `admin@raased.ma` | `Admin@123` |
| Manager LogiTrans | `manager@logitrans.ma` | `Manager@123` |
| Manager MediCargo | `manager@medicargo.ma` | `Manager@123` |
| Chauffeur LogiTrans | `driver@logitrans.ma` | `Driver@123` |
| Chauffeur MediCargo | `driver@medicargo.ma` | `Driver@123` |

Un chauffeur et un manager « invités » (sans mot de passe) existent également pour tester le
flux d'activation par email (`salma.idrissi@logitrans.ma`, `rachid.naciri@logitrans.ma`).

## 4. API principale

### Authentification

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/login` | Connexion email + mot de passe → `{ access_token, user }` |
| POST | `/api/auth/register` | Étape 1 : infos entreprise + responsable → envoie le code à l'email du **responsable** |
| POST | `/api/auth/register/resend` | Renvoie le code de vérification |
| POST | `/api/auth/register/verify` | Vérifie le **dernier** code envoyé → `{ password_token }` |
| POST | `/api/auth/register/complete` | Définit le mot de passe (+ confirmation) |
| POST | `/api/auth/organizations/:id/documents` | Upload des justificatifs (certificat entreprise, pièce d'identité) |
| POST | `/api/auth/forgot-password` | Vérifie l'email et envoie un code    |
| POST | `/api/auth/forgot-password/resend` | Renvoie le code    |
| POST | `/api/auth/forgot-password/verify` | Vérifie le **dernier** code → `{ password_token }` |
| POST | `/api/auth/forgot-password/reset` | Nouveau mot de passe + confirmation |
| GET | `/api/auth/invitations/validate?token=` | Valide un lien d'invitation |
| POST | `/api/auth/invitations/accept` | Active le compte invité (chauffeur ou manager) |
| GET | `/api/auth/me` | Profil du compte connecté (JWT) |

### Espaces
- **Admin** : `GET/PATCH /api/admin/organizations[...]`, `GET /api/admin/stats`, téléchargement des documents.
- **Manager** : `/api/managers/*` (overview, drivers, invite-manager, cargos, trackers, alerts).
- **Chauffeur** : `/api/drivers/*` (overview, trip, history, alerts).
- **Carte** : `GET /api/map/live` → convoyeurs en mouvement + corridors + zones (manager & chauffeur).

## 5. Structure

```
flask_api/
├── app.py            # Fabrique Flask, blueprints, création de la base
├── config.py         # Configuration via variables d'environnement
├── extensions.py     # db (SQLAlchemy) + CORS
├── models.py         # Modèles (users, organizations, codes, invitations,
│                     #   documents, cargos, trackers, positions, alertes, corridors, zones)
├── security.py       # bcrypt + JWT + décorateurs (rôles ADMIN/MANAGER/DRIVER)
├── service.py        # OTP, invitations, validation des codes
├── email_service.py  # E-mails (SMTP, sinon console en dev)
├── auth.py admin.py manager.py driver.py map_data.py   # Blueprints API
├── map_tools.py      # Calcul de positions simulées + tracés de routes
├── seed.py           # Données de démonstration
└── init_db.py        # Création de la base seule
```