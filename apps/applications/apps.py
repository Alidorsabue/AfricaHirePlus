from django.apps import AppConfig


class ApplicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.applications'
    verbose_name = 'Candidatures'

    def ready(self):
        import apps.applications.signals  # noqa: F401
