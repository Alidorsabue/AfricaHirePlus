"""
Settings développement - AfricaHirePlus ATS
"""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Base de données : PostgreSQL si configuré, sinon SQLite pour dev rapide
if os.environ.get('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'africahireplus'),
            'USER': os.environ.get('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5433'),
            'CONN_MAX_AGE': 60,
            'OPTIONS': {'connect_timeout': 10},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# CORS permissif en dev
CORS_ALLOW_ALL_ORIGINS = True
# Ou liste restreinte :
# CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

# Fichiers : stockage local
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Browsable API en dev
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Logs plus verbeux (app uniquement ; Hugging Face / filelock restent en WARNING)
LOGGING['root']['level'] = 'DEBUG'

# Email : console en dev (les messages s'affichent dans le terminal)
# Pour tester un vrai envoi : définir EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# et EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD dans .env
if os.environ.get('EMAIL_BACKEND'):
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
