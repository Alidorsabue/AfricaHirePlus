"""
Django base settings - AfricaHirePlus ATS
Partagées entre dev et prod.
"""
import os
from pathlib import Path
from datetime import timedelta

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Chargement .env (optionnel)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-change-me-in-production'
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',

    # Local apps (companies avant users : User.company FK)
    'apps.core',
    'apps.companies',
    'apps.users',
    'apps.jobs',
    'apps.candidates',
    'apps.applications.apps.ApplicationsConfig',
    'apps.tests',
    'apps.emails.apps.EmailsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'apps.core.middleware.RequestIPLoggingMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database - overridden in dev/prod
DATABASES = {}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media / fichiers uploadés (S3 en prod)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Limites d'upload pour CV et lettre de motivation (évite "Network Error" si fichiers trop lourds)
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 Mo
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 Mo

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Email — Configuration multi-provider
# ---------------------------------------------------------------------------
# Trois modes (sélection automatique selon les variables d'env) :
#   1. BREVO_API_KEY défini  → backend HTTP API Brevo (recommandé : tracking,
#      message-id, statistiques, webhooks possibles).
#   2. EMAIL_HOST défini     → backend SMTP classique (Brevo SMTP, Mailgun,
#      SES, etc.). Pour Brevo SMTP :
#          EMAIL_HOST=smtp-relay.brevo.com
#          EMAIL_PORT=587
#          EMAIL_USE_TLS=true
#          EMAIL_HOST_USER=<login Brevo (votre email)>
#          EMAIL_HOST_PASSWORD=<SMTP key Brevo>
#   3. Sinon                  → backend `console` (les emails s'affichent dans
#      les logs Django). Pratique en dev.
#
# La variable EMAIL_BACKEND peut TOUJOURS être forcée manuellement (overrides
# l'auto-détection).
# ---------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@africahireplus.com')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)  # Erreurs 500 / admins

BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '').strip()
BREVO_API_URL = os.environ.get('BREVO_API_URL', 'https://api.brevo.com/v3/smtp/email').strip()
BREVO_API_TIMEOUT = int(os.environ.get('BREVO_API_TIMEOUT', '15'))

EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'false').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_FROM_DISPLAY_NAME = os.environ.get('EMAIL_FROM_DISPLAY_NAME', '')
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '30'))

# Auto-détection du backend si EMAIL_BACKEND n'est pas explicitement défini.
_explicit_backend = os.environ.get('EMAIL_BACKEND', '').strip()
if _explicit_backend:
    EMAIL_BACKEND = _explicit_backend
elif BREVO_API_KEY:
    EMAIL_BACKEND = 'apps.emails.backends.BrevoApiBackend'
elif EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------------------------
# Configuration audit log emails (P9)
# ---------------------------------------------------------------------------
# Conservation des logs (jours) ; mettre 0 pour conserver sans limite. Une
# commande `python manage.py purge_old_email_logs` supprime les vieux logs.
EMAIL_LOG_RETENTION_DAYS = int(os.environ.get('EMAIL_LOG_RETENTION_DAYS', '90'))
# Activer le log d'audit (mettre à 'false' désactive complètement la création
# d'EmailLog — utile pour des envois massifs où la perf prime).
EMAIL_AUDIT_LOG_ENABLED = os.environ.get('EMAIL_AUDIT_LOG_ENABLED', 'true').lower() == 'true'

# Custom user model
AUTH_USER_MODEL = 'users.User'

# ---------------------------------------------------------------------------
# Django Rest Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'config.exceptions.custom_exception_handler',
    # P10.8 — Rate limiting (anti-spam, anti-DoS)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.environ.get('THROTTLE_ANON', '60/min'),
        'user': os.environ.get('THROTTLE_USER', '300/min'),
        # Scopes spécifiques (utilisés par ScopedRateThrottle dans certaines vues)
        'public_apply': os.environ.get('THROTTLE_PUBLIC_APPLY', '10/hour'),
        'export': os.environ.get('THROTTLE_EXPORT', '20/hour'),
        'bulk_status': os.environ.get('THROTTLE_BULK_STATUS', '60/hour'),
        'predict_score': os.environ.get('THROTTLE_PREDICT_SCORE', '120/hour'),
    },
}

# P10 — Tailles maximales des fichiers (Mo) — surchargeables par env
CV_MAX_SIZE_MB = int(os.environ.get('CV_MAX_SIZE_MB', 10))
COVER_LETTER_MAX_SIZE_MB = int(os.environ.get('COVER_LETTER_MAX_SIZE_MB', 5))
MLSCORE_MAX_PER_APPLICATION = int(os.environ.get('MLSCORE_MAX_PER_APPLICATION', 20))

# ---------------------------------------------------------------------------
# JWT (Simple JWT)
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ---------------------------------------------------------------------------
# CORS - overridden in dev/prod
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = []

# ---------------------------------------------------------------------------
# Frontend (utilisé pour générer les liens magiques : correcteur, etc.)
# ---------------------------------------------------------------------------
FRONTEND_BASE_URL = os.environ.get('FRONTEND_BASE_URL', '').rstrip('/')
# Chemin React-side de la page correcteur (token magique en query string).
CORRECTOR_LINK_PATH = os.environ.get('CORRECTOR_LINK_PATH', '/correct')

# ---------------------------------------------------------------------------
# AWS S3 (compatible MinIO, etc.) - config de base
# ---------------------------------------------------------------------------
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', '')
AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '')  # Pour MinIO
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN', '')
AWS_DEFAULT_ACL = 'private'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
AWS_QUERYSTRING_AUTH = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    # Réduire le bruit des libs tierces (Hugging Face, requêtes HTTP)
    'loggers': {
        'huggingface_hub': {'level': 'WARNING'},
        'filelock': {'level': 'WARNING'},
        'sentence_transformers': {'level': 'WARNING'},
        'urllib3': {'level': 'WARNING'},
        'requests': {'level': 'WARNING'},
    },
}
