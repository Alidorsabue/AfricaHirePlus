"""
Templates d'emails (multi-tenant par company) + audit log des envois.

P9 — Modélisation :
  - `EmailTemplate` : modèle paramétrable (sujet + corps HTML) par entreprise,
    avec variables Django (`{{ candidate_name }}`, etc.).
  - `EmailLog` : trace de TOUS les envois (audit, debug Brevo, retry).
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
        # P9 — Nouveaux types pour les workflows tests + correcteur externe
        TEST_SUBMITTED = 'test_submitted', 'Test soumis (recruteur)'
        TEST_EXPIRED = 'test_expired', 'Test expiré (candidat)'
        CORRECTOR_INVITATION = 'corrector_invitation', 'Invitation correcteur'
        CORRECTOR_REVOKED = 'corrector_revoked', 'Accès correcteur révoqué'
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


class EmailLog(TimeStampedMixin, models.Model):
    """
    Audit log de tous les emails envoyés via `apps.emails.services.dispatch_email`.

    Permet :
      - de savoir qui a reçu quoi et quand,
      - de retrouver le `message-id` Brevo pour debug ou webhook,
      - de tracer les échecs (rate-limit, domaine non vérifié, etc.).

    Conservation contrôlée par `EMAIL_LOG_RETENTION_DAYS` (commande
    `purge_old_email_logs`).
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        SENT = 'sent', 'Envoyé'
        FAILED = 'failed', 'Échec'
        SKIPPED = 'skipped', 'Ignoré'  # ex: template inactif, destinataire vide

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='email_logs',
        db_index=True,
    )
    template_type = models.CharField(
        max_length=40,
        blank=True, default='',
        db_index=True,
        help_text='Type d\'email (correspond à EmailTemplate.TemplateType).',
    )
    recipient_email = models.EmailField(max_length=254, db_index=True)
    subject = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    provider = models.CharField(
        max_length=40,
        blank=True, default='',
        help_text='backend utilisé (ex. "brevo_api", "smtp", "console").',
    )
    provider_message_id = models.CharField(
        max_length=255,
        blank=True, default='',
        db_index=True,
        help_text='Identifiant retourné par Brevo (header X-Message-Id).',
    )
    error_message = models.TextField(blank=True, default='')
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # FK optionnelles pour faciliter les requêtes / debug
    related_application_id = models.IntegerField(
        null=True, blank=True, db_index=True,
        help_text='ID de l\'Application liée (sans FK pour éviter les cycles).',
    )
    related_object_type = models.CharField(
        max_length=80, blank=True, default='',
        help_text='Type de l\'objet déclencheur (ex. "CorrectorAssignment").',
    )
    related_object_id = models.IntegerField(
        null=True, blank=True, db_index=True,
        help_text='ID de l\'objet déclencheur (assignment, grant, etc.).',
    )

    class Meta:
        db_table = 'emails_emaillog'
        verbose_name = 'Log d\'email'
        verbose_name_plural = 'Logs d\'emails'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['template_type', 'status']),
            models.Index(fields=['recipient_email', 'created_at']),
        ]

    def __str__(self):
        return f'{self.recipient_email} · {self.template_type or "?"} · {self.status}'
