from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.emails'
    verbose_name = 'Templates d’emails'

    def ready(self):
        import apps.emails.signals  # noqa: F401  # enregistre les signaux
