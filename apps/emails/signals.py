"""
Signals : à la création d'une entreprise, créer les templates d'email par défaut.
"""
import logging
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.companies.models import Company, CompanyLicense, generate_license_key
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


@receiver(post_save, sender=Company)
def company_post_save_create_license(sender, instance, created, **kwargs):
    """À la création d'une entreprise, attribue une licence unique (défaut 1 an), renouvelable."""
    if not created:
        return
    if hasattr(instance, 'license') and instance.license:
        return
    try:
        today = timezone.now().date()
        end_date = today + timedelta(days=12 * 30)  # 1 an par défaut
        CompanyLicense.objects.create(
            company=instance,
            license_key=generate_license_key(),
            duration_months=CompanyLicense.DURATION_1_YEAR,
            start_date=today,
            end_date=end_date,
        )
        logger.info('company_id=%s: licence créée (1 an par défaut).', instance.id)
    except Exception as e:
        logger.exception('Erreur création licence pour company_id=%s: %s', instance.id, e)
