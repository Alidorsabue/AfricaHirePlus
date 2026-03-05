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
2. Un nouveau service « PostgreSQL » apparaît. Il possède une variable **`DATABASE_URL`** (une longue URL avec mot de passe, host, etc.).  
   **Django a besoin de cette valeur** pour se connecter à la base. Voici comment la lui donner.

## 3. Variables d’environnement (obligatoires)

Cliquez sur votre **service web** (celui qui déploie le backend Django), puis ouvrez l’onglet **Variables**.

### Donner la base de données à Django (`DATABASE_URL`)

Deux façons, une seule suffit :

- **Méthode simple (copier-coller)**  
  1. Cliquez sur le service **PostgreSQL** (pas le web).  
  2. Onglet **Variables** (ou **Connect** / **Data**) : vous voyez `DATABASE_URL` avec une longue valeur. **Copiez toute la valeur** (ex. `postgresql://postgres:xxx@xxx.railway.app:5432/railway`).  
  3. Revenez au service **web** → **Variables** → **+ New variable**.  
  4. Nom : `DATABASE_URL`, Valeur : collez ce que vous avez copié.  
  → C’est tout. Django utilisera cette URL pour la base.

- **Méthode « référence »** (si vous préférez)  
  Dans le service **web** → **Variables** → **+ New variable** → **Add reference** (ou « Referenced variable »). Choisissez le service **PostgreSQL**, puis la variable **`DATABASE_URL`**. Railway mettra à jour la valeur automatiquement si la base change. Même résultat pour Django, juste une autre façon de faire.

### Autres variables à ajouter (toujours dans le service web)

| Variable | Valeur à mettre |
|----------|-----------------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `DJANGO_SECRET_KEY` | Une clé secrète longue (50+ caractères, générateur en ligne si besoin) |
| `ALLOWED_HOSTS` | Votre domaine Railway, ex. `votreservice.up.railway.app` (voir section 7 pour le générer) |
| `CORS_ALLOWED_ORIGINS` | L’URL de votre frontend, ex. `https://votreservice.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | L’URL de l’API, ex. `https://votreservice.up.railway.app` |

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

## 6. Déployer le frontend sur Railway (tout sur Railway)

**Oui, vous pouvez tout déployer sur Railway** : backend (Django), frontend (React/Vite) et PostgreSQL dans le **même projet**, avec **3 services** (ou 2 si vous aviez déjà déployé le backend).

### Pourquoi 2 services pour l’app (backend + frontend) ?

- Le **backend** est une app Python (Django + Gunicorn) qui expose l’API.
- Le **frontend** est une app Node (Vite) : on fait un build (fichiers statiques), puis on les sert avec un petit serveur.  
Railway déploie chaque “app” comme un **service**. Donc : 1 service = backend, 1 service = frontend. Même projet, deux déploiements.

### Étapes : ajouter le service frontend

1. **Backend déjà déployé**  
   Assurez-vous que le service Django tourne et que vous avez généré un domaine (section 7). Notez l’URL de l’API, ex. `https://africahireplus-api.up.railway.app`.

2. **Créer un second service (frontend)**  
   Dans le même projet Railway : **+ New** → **GitHub Repo** (ou **Empty Service** si vous préférez) → choisir **le même dépôt** AfricaHirePlus.

3. **Configurer le service frontend**  
   Cliquez sur ce nouveau service, puis **Settings** (ou **Variables** selon l’interface) :
   - **Root Directory** : `frontend`  
     (Railway build et démarrage se feront depuis le dossier `frontend/`.)
   - **Build Command** : `npm install && npm run build`  
   - **Start Command** : `npm run start`  
   (Le script `start` sert le dossier `dist/` sur le port `$PORT`.)

4. **Variable d’environnement pour l’API**  
   Dans ce service frontend, onglet **Variables** :
   - **Nom** : `VITE_API_URL`  
   - **Valeur** : l’URL de votre API **sans** slash final, avec le préfixe `/api/v1` si votre API est sous ce chemin.  
     Exemple : `https://africahireplus-api.up.railway.app/api/v1`  
   Cette valeur est utilisée **au moment du build** : le frontend appelle cette URL en production.

5. **Domaine du frontend**  
   Dans le service frontend : **Settings** → **Networking** → **Generate domain**. Vous obtenez une URL du type `https://xxx.up.railway.app`.

6. **CORS côté backend**  
   Dans le **service backend** (Django), onglet **Variables** :  
   - `CORS_ALLOWED_ORIGINS` doit contenir l’URL du frontend (ex. `https://xxx.up.railway.app`).  
   - `CSRF_TRUSTED_ORIGINS` doit contenir à la fois l’URL de l’API et celle du frontend si besoin (ex. `https://africahireplus-api.up.railway.app,https://xxx.up.railway.app`).  
   Redéployez le backend après modification des variables.

Après déploiement, vous avez **tout sur Railway** : une URL pour l’API (backend), une URL pour l’interface (frontend), et la base PostgreSQL dans le même projet.

## 7. Domaine personnalisé

Dans le service web : **Settings** → **Networking** → **Generate domain** (ex. `xxx.railway.app`) ou **Custom domain**. Mettez à jour `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS` en conséquence.

## Résumé des fichiers ajoutés pour Railway

- **Procfile** : commande de démarrage (migrate, collectstatic, gunicorn).
- **runtime.txt** : version Python (ex. 3.11).
- **config/settings/prod.py** : utilise `DATABASE_URL` si présente (Railway), sinon `POSTGRES_*` ; logging fichier optionnel.
- **config/settings/base.py** : middleware **WhiteNoise** pour servir les fichiers statiques.
- **requirements.txt** : `dj-database-url`, `gunicorn`, `whitenoise` déjà présents ou ajoutés.
