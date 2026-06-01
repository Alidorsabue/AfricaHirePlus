# AfricaHirePlus – ATS multi-entreprise (Afrique)

Plateforme ATS (Applicant Tracking System) multi-entreprise pour l’Afrique : offres d’emploi, candidatures, scoring ATS/ML, tests techniques, emails transactionnels et espace candidat (RGPD).

## Fonctionnalités principales

| Domaine | Capacités |
| -------- | ----------- |
| **Recrutement** | Offres, pipeline Kanban, shortlist simulée/générée, KPI, exports Excel |
| **Candidatures** | Postulation publique, screening, scores ATS, override manuel, machine d’états, notes internes, journal d’audit |
| **Candidats** | Profils multi-offres, tags, export/anonymisation RGPD, extraction CV multi-format |
| **Tests techniques** | QCM, texte, code, fichiers ; session chronométrée ; anti-triche ; correcteurs externes (token) |
| **Emails** | Templates par entreprise, envoi via Brevo (API ou SMTP), journal `EmailLog`, branding HTML |
| **Espaces** | Recruteur / Super admin / Candidat / Correcteur externe (portail `/correct`) |

## Stack

- **Backend :** Django 4.2+, Django REST Framework
- **Frontend :** React 19 (Vite), TypeScript, Tailwind CSS 4, TanStack Query, React Router, i18n (FR/EN)
- **Base de données :** PostgreSQL (SQLite possible en dev sans `POSTGRES_DB`)
- **Authentification :** JWT (Simple JWT) — login strict (tokens uniquement si l’utilisateur existe et est actif)
- **Stockage fichiers :** AWS S3 compatible (MinIO, etc.) ou disque local (`/media/`)
- **Emails :** Brevo API (recommandé), SMTP générique ou console (dev)
- **Déploiement :** [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) (Railway + PostgreSQL)

## Structure du projet

```
AfricaHirePlus/
├── config/                 # Settings Django (dev / prod), URLs, exceptions API
├── apps/
│   ├── core/               # Permissions, CV extraction, utilitaires
│   ├── users/              # User (super_admin, recruiter, candidate)
│   ├── companies/
│   ├── jobs/
│   ├── candidates/
│   ├── applications/       # Candidatures, ATS, notes, audit (P10)
│   ├── tests/              # Tests techniques, sessions, correcteurs (P1–P8)
│   └── emails/             # Templates, dispatch Brevo, EmailLog (P9)
├── frontend/               # SPA Vite — VITE_API_URL en prod
├── docs/                   # Documentation technique détaillée
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
# Éditer .env (python-dotenv signale les lignes invalides au chargement)
```

Pour exécuter des commandes avec **`config.settings.prod`** en local (ex. base Railway publique), installer les dépendances complètes (`pip install -r requirements.txt`, inclut `dj-database-url`).

## Base de données

**PostgreSQL (recommandé)** — dans `.env` :

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

**Dev sans PostgreSQL :** ne pas définir `POSTGRES_DB` → SQLite (`db.sqlite3`).

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

Super admin plateforme : `python manage.py create_superadmin` (voir [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)).

## Lancer le serveur (dev)

```bash
# Windows
set DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py runserver

# Linux/macOS
export DJANGO_SETTINGS_MODULE=config.settings.dev
python manage.py runserver
```

## Frontend (dev)

```bash
cd frontend
npm install
# Optionnel : frontend/.env avec VITE_API_URL=http://127.0.0.1:8000/api/v1
npm run dev
```

Build production : `npm run build` (définir **`VITE_API_URL`** au build, ex. `https://votre-api.up.railway.app/api/v1`).

### Routes principales (SPA)

| Chemin | Rôle | Description |
| ------ | ---- | ------------- |
| `/login`, `/register`, `/register/candidate` | Public | Connexion, inscription entreprise / candidat |
| `/offres/:slug`, `/offres/:slug/postuler` | Public | Fiche offre et candidature |
| `/` | Recruteur | Tableau de bord |
| `/jobs`, `/jobs/:id`, `/pipeline` | Recruteur | Offres, détail, pipeline |
| `/applications/:id` | Recruteur | Détail candidature (notes, audit, statut) |
| `/candidates`, `/candidates/:id` | Recruteur | Pool candidats, profil, tags |
| `/tests`, `/tests/:id/edit`, `/tests/results` | Recruteur | Gestion tests et résultats |
| `/emails` | Recruteur | Modèles d’emails transactionnels |
| `/correct` | Correcteur | Portail correction (lien magique token) |
| `/candidat`, `/candidat/offres`, `/candidat/profil` | Candidat | Candidatures, offres, profil RGPD |
| `/candidat/tests/:testId` | Candidat | Passage d’un test technique |

## API (`/api/v1/`)

En-tête après login : `Authorization: Bearer <access_token>`.

Les erreurs peuvent être encapsulées par le handler global (`success` / `error.details`) ; le frontend gère ces formats sur les écrans sensibles.

### Authentification

| Méthode | Route | Description |
| ------- | ----- | ----------- |
| POST | `/auth/token/` | Login JWT (`username`, `password` — souvent email pour les candidats) |
| POST | `/auth/token/refresh/` | Rafraîchir le token |
| GET/PATCH | `/auth/me/` | Profil utilisateur connecté |
| POST | `/auth/register/candidate/` | Inscription candidat |

### Candidatures (`/applications/`)

| Méthode | Route | Rôle |
| ------- | ----- | ---- |
| GET | `/` | Recruteur — liste |
| GET | `/mine/` | Candidat — liste **RGPD-safe** (sans scores détaillés ni notes internes) |
| POST | `/public/apply/` | Candidat — postuler (throttle) |
| POST | `/<id>/withdraw/` | Candidat — retirer sa candidature |
| PATCH | `/<id>/status/` | Recruteur — changement de statut (machine d’états + audit) |
| POST | `/bulk-status/` | Recruteur — mise à jour en masse (max 500) |
| GET/POST | `/<id>/notes/` | Recruteur — notes internes |
| GET | `/<id>/audit/` | Recruteur — journal d’audit |
| POST | `/<id>/run-screening/`, `/<id>/predict-score/` | Recruteur — screening / score ML |

### Candidats (`/candidates/`)

| Méthode | Route | Rôle |
| ------- | ----- | ---- |
| GET/PATCH | `/me/` | Candidat — mon profil |
| GET | `/me/export/` | Candidat — export JSON (portabilité RGPD) |
| DELETE | `/me/` | Candidat — anonymisation (effacement) |
| PATCH | `/<id>/tags/` | Recruteur — tags libres |
| POST | `/<id>/anonymize/` | Recruteur — anonymiser un profil |

### Tests (`/tests/`)

| Méthode | Route | Rôle |
| ------- | ----- | ---- |
| GET/POST | `/` | Recruteur — CRUD tests |
| GET | `/<id>/take/?application_id=` | Candidat — test **sans** bonnes réponses |
| POST | `/start-session/`, `/auto-save/`, `/submit-answers/` | Candidat — session |
| GET | `/results/`, `/results/<id>/report.pdf` | Recruteur — résultats et rapports |
| POST | `/answers/<id>/review/` | Recruteur — correction manuelle |
| * | `/correctors/...` | Correcteur externe (token magique) |

### Autres ressources

- **Companies :** `/companies/`
- **Jobs :** `/jobs/` (+ routes publiques `/jobs/public/`, shortlist, KPI, exports)
- **Emails :** `/emails/templates/`

Liste complète des endpoints P10 : [docs/APPLICATIONS_CANDIDATES_HARDENING.md](docs/APPLICATIONS_CANDIDATES_HARDENING.md#11-endpoints-récapitulatifs).

## Multi-tenant

- Chaque **recruteur** est lié à une **entreprise** et ne voit que les données de son tenant.
- Les **super_admin** voient toutes les entreprises.
- Les **candidats** accèdent à leur espace (offres, candidatures, tests éligibles).
- Filtrage `company_id` dans les `get_queryset()` ; permissions strictes (`IsRecruiterOrAdmin`, `IsOwnerCandidate`, etc.).

## Soft delete

Les modèles avec `SoftDeleteMixin` ne sont pas supprimés physiquement : `deleted_at` est renseigné. Le `SoftDeleteManager` les exclut par défaut.

## Extraction CV (moteur v2)

Module `apps.core.cv_extraction` — extraction texte multi-format avec fallback automatique :

- **Formats :** PDF, DOCX, DOC, ODT, RTF, TXT, JPG, PNG, WEBP, TIFF, BMP
- **Pipeline PDF :** pypdf → pdfminer.six → OCR Tesseract (PDF scannés)
- **Sortie :** `ExtractionResult(text, method, quality_score, ocr_used, warnings, …)`
- **Compat :** `extract_text_from_uploaded_file(upload) -> str`

```bash
pip install pdfminer.six docx2txt odfpy striprtf   # formats étendus
pip install pdf2image pytesseract                  # OCR
```

Tesseract : [installation](https://tesseract-ocr.github.io/tessdoc/Installation.html) (paquets `fra` + `eng` recommandés).

## Configuration utile (`.env`)

| Variable | Description |
| -------- | ----------- |
| `BREVO_API_KEY` | Envoi emails via API Brevo (prod) |
| `DEFAULT_FROM_EMAIL`, `FRONTEND_BASE_URL` | Expéditeur et liens dans les emails |
| `CV_MAX_SIZE_MB`, `COVER_LETTER_MAX_SIZE_MB` | Limites upload candidature (déf. 10 / 5 Mo) |
| `THROTTLE_PUBLIC_APPLY`, `THROTTLE_BULK_STATUS`, … | Rate limiting DRF |
| `USE_S3`, `AWS_*` | Stockage médias S3/MinIO |

Voir [docs/EMAILS_BREVO.md](docs/EMAILS_BREVO.md) et [docs/CONFIGURATION_SMTP.md](docs/CONFIGURATION_SMTP.md).

## Documentation technique

| Document | Sujet |
| -------- | ----- |
| [docs/APPLICATIONS_CANDIDATES_HARDENING.md](docs/APPLICATIONS_CANDIDATES_HARDENING.md) | P10 — permissions, workflow, audit, RGPD, notes, tags |
| [docs/TESTS_MODULE_HARDENING.md](docs/TESTS_MODULE_HARDENING.md) | Tests techniques — sécurité candidat, sessions, correcteurs |
| [docs/EMAILS_BREVO.md](docs/EMAILS_BREVO.md) | Pipeline emails, templates, `EmailLog` |
| [docs/MATCHING_HARDENING.md](docs/MATCHING_HARDENING.md) | Matching candidat / offre |
| [docs/ATS_SCORE_ANALYSIS.md](docs/ATS_SCORE_ANALYSIS.md) | Analyse des scores ATS |
| [docs/ML_ARCHITECTURE.md](docs/ML_ARCHITECTURE.md) | Architecture scoring ML |
| [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) | Déploiement Railway |

## Tests automatisés

```bash
# Module candidatures / candidats (P10)
python manage.py test apps.applications.tests_p10_hardening --keepdb

# Module tests techniques
python manage.py test apps.tests --keepdb

# Emails
python manage.py test apps.emails --keepdb
```

## Production

- **`DJANGO_SETTINGS_MODULE=config.settings.prod`**
- **`DJANGO_SECRET_KEY`**, **`ALLOWED_HOSTS`**, **`CORS_ALLOWED_ORIGINS`**, **`CSRF_TRUSTED_ORIGINS`**
- Base : **`DATABASE_URL`** (Railway) ou variables `POSTGRES_*`
- Fichiers : `USE_S3=true` et variables AWS/MinIO si besoin

Guide pas à pas : [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md).

**Note :** l’hôte `postgres.railway.internal` dans `DATABASE_URL` n’est joignable que depuis le réseau Railway. Pour inspecter la base depuis votre PC, utilisez l’URL PostgreSQL **publique** du dashboard Railway.
