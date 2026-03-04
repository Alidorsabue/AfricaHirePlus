# Déploiement AfricaHirePlus sur Railway

Ce guide décrit comment mettre l’API Django en production sur [Railway](https://railway.app).

## Prérequis

- Compte [Railway](https://railway.app)
- Projet relié à un dépôt Git (GitHub/GitLab)

## 1. Créer un projet Railway

1. Sur [railway.app](https://railway.app), **New Project**.
2. **Deploy from GitHub repo** et sélectionnez le dépôt AfricaHirePlus.
3. Railway détecte le **Procfile** et configure le service web.

## 2. Ajouter PostgreSQL

1. Dans le projet, **+ New** → **Database** → **PostgreSQL**.
2. Une fois créé, Railway expose automatiquement **`DATABASE_URL`** (et variables liées). Inutile de la renseigner à la main si le service DB est lié au service Django.

## 3. Variables d’environnement (obligatoires)

Dans le service **web** (Django) : **Variables** et définir au minimum :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `DJANGO_SETTINGS_MODULE` | Module Django en prod | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | Clé secrète (min. 50 caractères) | Chaîne aléatoire forte |
| `ALLOWED_HOSTS` | Domaines autorisés (séparés par des virgules) | `*.railway.app,votredomaine.com` |
| `CORS_ALLOWED_ORIGINS` | Origines CORS (frontend) | `https://votre-app.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | Origines de confiance CSRF | `https://votre-api.railway.app` |

### Lier la base au service web

- Si la base est dans le **même projet** : **Variables** du service web → **Add variable** → **Add a reference** → choisir la variable **`DATABASE_URL`** du service PostgreSQL.  
  Ainsi, `DATABASE_URL` est injectée automatiquement, pas besoin de la copier.

### Optionnel (emails, S3, etc.)

- **Emails** : `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, etc. (voir `.env.example`).
- **Fichiers (S3)** : `USE_S3=true`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, etc.
- **Log fichier** : laisser `LOG_FILE` non défini sur Railway (logs = console uniquement). Si vous avez un volume, vous pouvez définir `LOG_FILE=/chemin/vers/django.log`.

## 4. Déploiement

- À chaque push sur la branche suivie, Railway build et déploie.
- Au démarrage, le **Procfile** exécute :
  1. `python manage.py migrate --noinput`
  2. `python manage.py collectstatic --noinput`
  3. `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`

Le **port** est fourni par Railway via `$PORT`.

## 5. Premier superutilisateur

En local (avec `DATABASE_URL` ou `POSTGRES_*` pointant vers la base Railway) :

```bash
set DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py createsuperuser
```

Ou via **Railway CLI** : ouvrir un shell du service et lancer la même commande après avoir exporté `DJANGO_SETTINGS_MODULE=config.settings.prod`.

## 6. Frontend (React/Vite)

L’API Django est déployée seule sur Railway. Le frontend peut être :

- **Option A** : Déployé sur un autre service Railway (build Vite, servir les fichiers statiques) ou sur Vercel/Netlify.
- **Option B** : Build intégré au repo (ex. script de build dans `frontend/`) et servi par un second service Railway qui sert le build (ex. nginx ou `vite preview` en prod).

Pensez à mettre à jour `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` avec l’URL réelle du frontend en production.

## 7. Domaine personnalisé

Dans le service web : **Settings** → **Networking** → **Generate domain** (ex. `xxx.railway.app`) ou **Custom domain**. Mettez à jour `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` en conséquence.

## Résumé des fichiers ajoutés pour Railway

- **Procfile** : commande de démarrage (migrate, collectstatic, gunicorn).
- **runtime.txt** : version Python (ex. 3.11).
- **config/settings/prod.py** : utilise `DATABASE_URL` si présente (Railway), sinon `POSTGRES_*` ; logging fichier optionnel.
- **config/settings/base.py** : middleware **WhiteNoise** pour servir les fichiers statiques.
- **requirements.txt** : `dj-database-url`, `gunicorn`, `whitenoise` déjà présents ou ajoutés.
