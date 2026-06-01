# AfricaHirePlus – ATS multi-entreprise (Afrique)

Plateforme ATS (Applicant Tracking System) multi-entreprise pour l’Afrique.

## Stack

- **Backend :** Django 4.2+, Django REST Framework
- **Frontend :** React (Vite), TypeScript, Tailwind, React Query, i18n
- **Base de données :** PostgreSQL (SQLite possible en dev sans `POSTGRES_DB`)
- **Authentification :** JWT (Simple JWT) — endpoint de login strict (tokens uniquement si l’utilisateur existe et est actif)
- **Stockage fichiers :** AWS S3 compatible (MinIO, etc.)
- **Déploiement :** voir [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) (Railway + PostgreSQL)

## Structure du projet

```
AfricaHirePlus/
├── config/                 # Configuration projet
│   ├── settings/
│   │   ├── base.py         # Settings communs
│   │   ├── dev.py          # Développement
│   │   └── prod.py         # Production (DATABASE_URL, dj-database-url)
│   ├── urls.py
│   ├── exceptions.py       # Handler d’exceptions API
│   └── storages.py         # S3 (médias)
├── apps/
│   ├── core/
│   ├── users/              # User (SuperAdmin, Recruiter, Candidate)
│   ├── companies/
│   ├── jobs/
│   ├── candidates/
│   ├── applications/
│   ├── tests/
│   └── emails/
├── frontend/               # SPA (Vite) — variable VITE_API_URL en prod
├── manage.py               # défaut : config.settings.dev
├── requirements.txt
└── .env.example
```

## Installation (backend)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
cp .env.example .env
# Éditer .env (éviter les lignes invalides : python-dotenv les signale au chargement)
```

Pour exécuter des commandes avec **`config.settings.prod`** en local (ex. base Railway publique), il faut que `dj-database-url` soit installé (`pip install -r requirements.txt`).

## Base de données

**PostgreSQL (recommandé) :** dans `.env` :

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

**Dev sans PostgreSQL :** ne pas définir `POSTGRES_DB` → SQLite (`db.sqlite3`).

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

Création d’un super admin plateforme : `python manage.py create_superadmin` (voir [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)).

## Lancer le serveur (dev)

```bash
export DJANGO_SETTINGS_MODULE=config.settings.dev   # Linux/macOS
set DJANGO_SETTINGS_MODULE=config.settings.dev      # Windows
python manage.py runserver
```

## Frontend (dev)

```bash
cd frontend
npm install
# Optionnel : .env avec VITE_API_URL=http://127.0.0.1:8000/api/v1
npm run dev
```

En production, définir **`VITE_API_URL`** au build (ex. `https://votre-api.up.railway.app/api/v1`) pour que les appels API pointent vers le bon backend.

## API

- **Login JWT :** `POST /api/v1/auth/token/` — corps JSON : `username`, `password` (les candidats inscrits par email ont souvent `username` = email)
- **Refresh :** `POST /api/v1/auth/token/refresh/`
- **Profil :** `GET/PATCH /api/v1/auth/me/` (Bearer requis)
- **Companies :** `/api/v1/companies/`
- **Jobs :** `/api/v1/jobs/`
- **Candidates :** `/api/v1/candidates/`
- **Applications :** `/api/v1/applications/`
- **Tests :** `/api/v1/tests/`, `/api/v1/tests/results/`
- **Emails :** `/api/v1/emails/templates/`

En-tête après login : `Authorization: Bearer <access_token>`.

Les erreurs API peuvent être encapsulées par le handler (`success` / `error.details`) ; le frontend gère ces formats sur les écrans sensibles (ex. connexion).

## Multi-tenant

- Chaque **Recruiter** est lié à une **Company** et ne voit que les données de son entreprise.
- Les **SuperAdmin** voient toutes les companies et toutes les données.
- Les **Candidate** accèdent à l’espace candidat (offres, candidatures).
- Filtrage par `company_id` dans les `get_queryset()` des vues recruteur.

## Soft delete

Les modèles qui héritent de `SoftDeleteMixin` ne sont pas supprimés physiquement : le champ `deleted_at` est renseigné. Le `SoftDeleteManager` exclut ces enregistrements par défaut.

## Extraction CV (moteur v2)

Module `apps.core.cv_extraction` — extraction texte multi-format avec fallback automatique :

- **Formats** : PDF, DOCX, DOC, ODT, RTF, TXT, JPG, PNG, WEBP, TIFF, BMP
- **Pipeline PDF** : pypdf → pdfminer.six → OCR Tesseract (PDF scannés)
- **Détection** : magic bytes > extension > content_type
- **Sortie enrichie** : `ExtractionResult(text, method, page_count, quality_score, ocr_used, warnings, metadata)`
- **Compat v1** : `extract_text_from_uploaded_file(upload) -> str` toujours disponible

### Dépendances optionnelles

Le cœur (PDF natif + DOCX) est inclus dans `requirements.txt`. Les extras sont **lazy-importés** (pas de crash s'ils manquent, seulement un warning dans `result.warnings`) :

```bash
pip install pdfminer.six docx2txt odfpy striprtf            # formats étendus
pip install pdf2image pytesseract                            # OCR (PDF scannés + images)
```

Le binaire **Tesseract** doit être installé pour l'OCR :
- Windows : [tesseract-ocr.github.io](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- Linux : `apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng`
- macOS : `brew install tesseract tesseract-lang`

### Utilisation

```python
from apps.core.cv_extraction import extract_cv

result = extract_cv(uploaded_file, filename=upload.name, content_type=upload.content_type)
if result.is_sufficient:
    candidate.raw_cv_text = result.text
# result.method.value, result.quality_score, result.warnings disponibles pour audit
```

## Production

- **`DJANGO_SETTINGS_MODULE=config.settings.prod`**
- **`DJANGO_SECRET_KEY`**, **`ALLOWED_HOSTS`**, **`CORS_ALLOWED_ORIGINS`**, **`CSRF_TRUSTED_ORIGINS`**
- Base : **`DATABASE_URL`** (Railway) ou variables `POSTGRES_*`
- Fichiers : `USE_S3=true` et variables AWS/MinIO si besoin

Guide pas à pas : [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md).

**Note :** l’hôte `postgres.railway.internal` dans `DATABASE_URL` n’est joignable que depuis le réseau Railway. Pour des requêtes Django depuis votre PC, utilisez l’URL PostgreSQL **publique** du dashboard Railway si vous devez inspecter la base localement.
