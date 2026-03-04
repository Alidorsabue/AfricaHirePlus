"""
Signals : à la création d'une entreprise, créer les templates d'email par défaut.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.companies.models import Company
from apps.emails.default_templates import create_default_templates_for_company

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Company)
def company_post_save_create_default_email_templates(sender, instance, created, **kwargs):
    """À la création d'une entreprise, crée les templates d'email par défaut (candidature reçue, shortlist, refus)."""
    if not created:
        return
    try:
        n = create_default_templates_for_company(instance)
        if n > 0:
            logger.info('company_id=%s: %s template(s) d’email par défaut créé(s).', instance.id, n)
    except Exception as e:
        logger.exception('Erreur création templates email pour company_id=%s: %s', instance.id, e)
