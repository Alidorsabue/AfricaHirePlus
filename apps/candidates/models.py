"""
Candidats (pool par entreprise - multi-tenant).
Chaque entreprise a son propre pool de candidats ; un candidat est unique par (company, email).
"""
from django.conf import settings
from django.db import models

from apps.companies.models import Company
from apps.core.models import SoftDeleteMixin, TimeStampedMixin


class Candidate(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Candidat rattaché au pool d'une entreprise. Peut être lié à un User (compte candidat)."""

    # — Lien compte utilisateur (optionnel) et entreprise propriétaire du pool —
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='candidate_profiles',
        help_text='Compte candidat (si inscrit sur la plateforme).',
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='candidates',
        db_index=True,
    )
    # — Identité de base —
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=100, db_index=True)
    last_name = models.CharField(max_length=100, db_index=True)
    phone = models.CharField(max_length=30, blank=True)

    # Détails personnels (canevas candidature)
    title = models.CharField(max_length=20, blank=True, help_text='Civilité: Mr, Mrs, Ms, Dr')
    preferred_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, blank=True, db_index=True)
    address = models.CharField(max_length=500, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    postcode = models.CharField(max_length=20, blank=True)
    cell_number = models.CharField(max_length=30, blank=True)
    nationality = models.CharField(max_length=100, blank=True, db_index=True)
    second_nationality = models.CharField(max_length=100, blank=True)

    # CV / profil
    resume = models.FileField(upload_to='candidates/resumes/%Y/%m/', null=True, blank=True)
    linkedin_url = models.URLField(max_length=500, blank=True)
    portfolio_url = models.URLField(max_length=500, blank=True)
    summary = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(null=True, blank=True, db_index=True)
    education_level = models.CharField(max_length=50, blank=True, db_index=True)
    current_position = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True, db_index=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)

    # Données structurées (pour screening)
    skills = models.JSONField(default=list, blank=True)  # ["Python", "Django"]
    raw_cv_text = models.TextField(blank=True, help_text='Texte extrait du CV pour recherche')

    # Formation, expérience, langues, références (JSON)
    education = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Liste de formations: education_type, degree_type, discipline, other_specializations, '
            'country, institution, city_campus, study_level, enrollment_status, start_year, end_year'
        ),
    )
    experience = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Liste d’expériences: employment_status, employment_type, job_title, job_contract_type, '
            'responsibilities, start_month, start_year, company_name, company_sector, country, city, '
            'department, manager_name, etc.'
        ),
    )
    languages = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Liste de langues: language, speaking_proficiency, reading_proficiency, writing_proficiency '
            '(e.g. fluent, proficient, intermediate, basic, elementary)'
        ),
    )
    references = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Liste de références: first_name, last_name, organization, job_title, phone, email'
        ),
    )

    class Meta:
        db_table = 'candidates_candidate'
        verbose_name = 'Candidat'
        verbose_name_plural = 'Candidats'
        unique_together = [['company', 'email']]  # Un seul candidat par email par entreprise
        indexes = [
            models.Index(fields=['company', 'email']),
            models.Index(fields=['company', 'deleted_at']),
            models.Index(fields=['country', 'experience_years']),
        ]

    def __str__(self):
        return f'{self.get_full_name()} ({self.email})'

    def get_full_name(self):
        """Retourne prénom + nom ou email si vide."""
        return f'{self.first_name} {self.last_name}'.strip() or self.email
