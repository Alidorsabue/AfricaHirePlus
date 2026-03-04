# AfricaHirePlus – ATS Multi-entreprise (Afrique)

Plateforme ATS (Applicant Tracking System) multi-entreprise pour l’Afrique.

## Stack

- **Backend:** Django 4.2+
- **API:** Django Rest Framework
- **Base de données:** PostgreSQL (SQLite possible en dev)
- **Authentification:** JWT (Simple JWT)
- **Stockage fichiers:** AWS S3 compatible (MinIO, etc.)
- **Versioning:** Git

## Structure du projet

```
AfricaHirePlus/
├── config/                 # Configuration projet
│   ├── settings/
│   │   ├── base.py         # Settings communs
│   │   ├── dev.py          # Développement
│   │   └── prod.py         # Production
│   ├── urls.py
│   ├── exceptions.py       # Handler d’exceptions API
│   └── storages.py        # S3 (médias)
├── apps/
│   ├── core/               # Mixins (SoftDelete, TimeStamped)
│   ├── users/              # User (SuperAdmin, Recruiter)
│   ├── companies/          # Company (multi-tenant)
│   ├── jobs/               # JobOffer, ScreeningRule
│   ├── candidates/         # Candidate
│   ├── applications/      # Application
│   ├── tests/              # Test, Question, CandidateTestResult
│   └── emails/             # EmailTemplate
├── manage.py
├── requirements.txt
└── .env.example
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
# Éditer .env (optionnel en dev)
```

## Base de données

**PostgreSQL (recommandé):** définir dans `.env` :

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

**Dev sans PostgreSQL :** ne pas définir `POSTGRES_DB` → SQLite (`db.sqlite3`) sera utilisé.

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## Lancer le serveur

```bash
export DJANGO_SETTINGS_MODULE=config.settings.dev   # Linux/macOS
set DJANGO_SETTINGS_MODULE=config.settings.dev      # Windows
python manage.py runserver
```

## API

- **Auth JWT:** `POST /api/v1/auth/token/` (email + password) → access/refresh
- **Refresh:** `POST /api/v1/auth/token/refresh/`
- **Profil:** `GET/PATCH /api/v1/auth/me/`
- **Companies:** `/api/v1/companies/`
- **Jobs:** `/api/v1/jobs/`
- **Candidates:** `/api/v1/candidates/`
- **Applications:** `/api/v1/applications/`
- **Tests:** `/api/v1/tests/`, `/api/v1/tests/results/`
- **Emails:** `/api/v1/emails/templates/`

En-tête requis (après login) : `Authorization: Bearer <access_token>`.

## Multi-tenant

- Chaque **Recruiter** est lié à une **Company** et ne voit que les données de son entreprise.
- Les **SuperAdmin** voient toutes les companies et toutes les données.
- Filtrage par `company_id` dans les `get_queryset()` des vues.

## Soft delete

Les modèles qui héritent de `SoftDeleteMixin` (Company, JobOffer, Candidate, Application, etc.) ne sont pas réellement supprimés : le champ `deleted_at` est renseigné. Pour les exclure par défaut, utiliser le `SoftDeleteManager` (déjà utilisé sur ces modèles).

## Production

- Utiliser `config.settings.prod`.
- Définir `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, variables PostgreSQL.
- Pour les fichiers : `USE_S3=true` et variables AWS/MinIO dans `.env`.
