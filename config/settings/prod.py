"""
Settings production - AfricaHirePlus ATS
Sécurité renforcée, S3, CORS restreint.
Compatible Railway (DATABASE_URL) et PostgreSQL classique (POSTGRES_*).
"""
import os
from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')
if not any(ALLOWED_HOSTS):
    ALLOWED_HOSTS = ['*']  # À remplacer par vos domaines (ex. .railway.app)

# Base de données : DATABASE_URL (Railway) ou POSTGRES_* (manuel)
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, conn_health_checks=True)
    }
    opts = DATABASES['default'].setdefault('OPTIONS', {})
    opts['connect_timeout'] = 20
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB'),
            'USER': os.environ.get('POSTGRES_USER'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
            'HOST': os.environ.get('POSTGRES_HOST'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'connect_timeout': 20,
                'sslmode': os.environ.get('POSTGRES_SSLMODE', 'prefer'),
            },
        }
    }

# Sécurité
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ValueError('DJANGO_SECRET_KEY must be set in production')

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'true').lower() == 'true'
# Derrière Railway (ou tout proxy HTTPS), Django doit faire confiance à X-Forwarded-Proto
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

# CORS restreint (origines exactes : https://votredomaine.com — pas de slash final)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

# Stockage S3 (AWS ou compatible)
USE_S3 = os.environ.get('USE_S3', 'false').lower() == 'true'
if USE_S3 and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY and AWS_STORAGE_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = 'config.storages.MediaS3Storage'
    # Optionnel : static files sur S3
    # STATICFILES_STORAGE = 'config.storages.StaticS3Storage'

# Email : SMTP en production si configuré (sinon console pour éviter crash)
if os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Pas de Browsable API en prod
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
]

# Logging : fichier si LOG_FILE défini (sinon console uniquement, adapté Railway)
_log_file = os.environ.get('LOG_FILE')
if _log_file:
    _log_dir = os.path.dirname(_log_file)
    if _log_dir and os.path.isdir(_log_dir):
        LOGGING['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': _log_file,
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        }
        LOGGING['root']['handlers'] = ['console', 'file']
