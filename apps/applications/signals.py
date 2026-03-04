"""
Signal : à chaque création d'Application, lancer la présélection automatique si l'offre est ouverte.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.applications.models import Application
from apps.jobs.models import JobOffer
from apps.jobs.services import compute_preselection


@receiver(post_save, sender=Application)
def application_post_save_preselection(sender, instance, created, **kwargs):
    """À la création d'une candidature, si l'offre est ouverte (PUBLISHED), calculer preselection_score et statut."""
    if not created:
        return
    if instance.job_offer.status != JobOffer.Status.PUBLISHED:
        return
    compute_preselection(instance)
