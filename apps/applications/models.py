"""
Candidatures : lien Candidate <-> JobOffer (multi-tenant via job_offer.company).
Une candidature = un candidat postule à une offre ; statut et score de screening.
"""
from django.db import models

from apps.core.models import SoftDeleteMixin, TimeStampedMixin
from apps.jobs.models import JobOffer
from apps.candidates.models import Candidate


class Application(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Candidature d'un candidat à une offre. Workflow : applied → preselected → shortlisted → rejected / hired."""

    class Status(models.TextChoices):
        APPLIED = 'applied', 'Postulé'
        PRESELECTED = 'preselected', 'Pré-sélectionné'
        REJECTED_PRESELECTION = 'rejected_preselection', 'Refusé (présélection)'
        SHORTLISTED = 'shortlisted', 'Shortlisté'
        REJECTED_SELECTION = 'rejected_selection', 'Refusé (sélection)'
        INTERVIEW = 'interview', 'En entretien'
        OFFER = 'offer', 'Offre envoyée'
        HIRED = 'hired', 'Embauché'
        REJECTED = 'rejected', 'Refusé'
        WITHDRAWN = 'withdrawn', 'Retirée'

    # — Offre et candidat (unicité couple offre/candidat) —
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name='applications',
        db_index=True,
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='applications',
        db_index=True,
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.APPLIED,
        db_index=True,
    )
    # — Lettre de motivation, signature, source, scoring —
    cover_letter = models.TextField(blank=True)
    cover_letter_document = models.FileField(
        upload_to='applications/cover_letters/%Y/%m/',
        null=True,
        blank=True,
    )
    signature_text = models.CharField(
        max_length=255,
        blank=True,
        help_text='Signature électronique : Prénom Nom ou email',
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=100, blank=True, db_index=True)  # site, import, etc.
    screening_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Score de matching avec les règles de screening (legacy, voir preselection_score)',
    )
    preselection_score = models.FloatField(null=True, blank=True)
    selection_score = models.FloatField(null=True, blank=True)
    preselection_score_details = models.JSONField(
        null=True,
        blank=True,
        help_text='Détail par critère (criterion, passed, weight_awarded) pour transparence RH',
    )
    selection_score_details = models.JSONField(
        null=True,
        blank=True,
        help_text='Détail par critère (criterion, passed, weight_awarded) pour transparence RH',
    )
    is_manually_adjusted = models.BooleanField(default=False)
    manual_override_reason = models.TextField(null=True, blank=True)
    manually_added_to_shortlist = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'applications_application'
        verbose_name = 'Candidature'
        verbose_name_plural = 'Candidatures'
        unique_together = [['job_offer', 'candidate']]
        indexes = [
            models.Index(fields=['job_offer', 'status']),
            models.Index(fields=['candidate', 'status']),
            models.Index(fields=['status', 'applied_at']),
        ]

    def __str__(self):
        return f'{self.candidate.get_full_name()} → {self.job_offer.title}'

    @property
    def company_id(self):
        """ID entreprise (via l'offre) pour vérification des permissions multi-tenant."""
        return self.job_offer.company_id


class MLScore(TimeStampedMixin, models.Model):
    """
    Score prédictif ML pour une candidature. Versioning et traçabilité pour audit et re-training.
    Chaque prédiction enregistre model_version et date pour reproductibilité.
    """
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='ml_scores',
        db_index=True,
    )
    model_version = models.CharField(
        max_length=64,
        db_index=True,
        help_text='Version du modèle utilisé (ex: v1.0.0, 20250226-stub)',
    )
    predicted_score = models.FloatField(
        help_text='Score prédit par le modèle (0–100)',
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text='Confiance du modèle (0–1), optionnel',
    )
    features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text='Features utilisées pour la prédiction (feature store)',
    )
    ml_explanation_json = models.JSONField(
        null=True,
        blank=True,
        help_text='Explications IA (SHAP, feature importance, etc.) pour interprétabilité future',
    )
    # created_at fourni par TimeStampedMixin

    class Meta:
        db_table = 'applications_mlscore'
        verbose_name = 'Score ML'
        verbose_name_plural = 'Scores ML'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application', 'created_at']),
            models.Index(fields=['model_version', 'created_at']),
        ]

    def __str__(self):
        return f'MLScore {self.predicted_score:.1f} (v{self.model_version}) — App #{self.application_id}'
