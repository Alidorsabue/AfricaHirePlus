"""
Templates d'emails (multi-tenant par company).
Un template par type et par entreprise : candidature reçue, refus, shortlist, etc.
"""
from django.db import models

from apps.companies.models import Company
from apps.core.models import SoftDeleteMixin, TimeStampedMixin


class EmailTemplate(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Modèle d'email : sujet + corps HTML avec variables {{ candidate_name }}, {{ job_title }}, etc."""

    class TemplateType(models.TextChoices):
        APPLICATION_RECEIVED = 'application_received', 'Candidature reçue'
        APPLICATION_REJECTED = 'application_rejected', 'Candidature refusée'
        SHORTLIST_NOTIFICATION = 'shortlist_notification', 'Notification shortlist'
        INTERVIEW_INVITATION = 'interview_invitation', 'Invitation entretien'
        OFFER_LETTER = 'offer_letter', 'Lettre d\'offre'
        TEST_INVITATION = 'test_invitation', 'Invitation test'
        REMINDER = 'reminder', 'Relance'
        CUSTOM = 'custom', 'Personnalisé'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='email_templates',
        db_index=True,
    )
    name = models.CharField(max_length=150, db_index=True)
    template_type = models.CharField(
        max_length=30,
        choices=TemplateType.choices,
        default=TemplateType.CUSTOM,
        db_index=True,
    )
    subject = models.CharField(max_length=255)
    body_html = models.TextField(
        blank=True,
        default='',
        help_text='HTML avec variables: {{ candidate_name }}, {{ job_title }}, etc.',
    )
    body_text = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'emails_emailtemplate'
        verbose_name = 'Template d\'email'
        verbose_name_plural = 'Templates d\'emails'
        unique_together = [['company', 'template_type']]
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]

    def __str__(self):
        return f'{self.name} ({self.company.name})'
