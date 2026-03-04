"""
Offres d'emploi et règles de screening (multi-tenant par company).
Chaque offre appartient à une entreprise ; slug unique par company.
"""
from django.db import models

from apps.companies.models import Company
from apps.core.models import SoftDeleteMixin, TimeStampedMixin


class JobOffer(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Offre d'emploi : titre, description, type de contrat, statut (brouillon/publiée/clôturée), rémunération."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        PUBLISHED = 'published', 'Publiée'
        CLOSED = 'closed', 'Clôturée'
        ARCHIVED = 'archived', 'Archivée'

    class ContractType(models.TextChoices):
        CDI = 'cdi', 'CDI'
        CDD = 'cdd', 'CDD'
        FREELANCE = 'freelance', 'Freelance'
        INTERNSHIP = 'internship', 'Stage'
        PART_TIME = 'part_time', 'Temps partiel'
        OTHER = 'other', 'Autre'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='job_offers',
        db_index=True,
    )
    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=120, db_index=True)  # Unique par company, pour URL publique
    description = models.TextField(
        blank=True,
        help_text='Optionnel si un document est joint.',
    )
    description_document = models.FileField(
        upload_to='jobs/documents/%Y/%m/',
        blank=True,
        null=True,
        help_text='PDF ou Word : fiche offre à afficher aux candidats.',
    )
    requirements = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True, db_index=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)
    contract_type = models.CharField(
        max_length=20,
        choices=ContractType.choices,
        default=ContractType.CDI,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='XOF', blank=True)
    salary_visible = models.BooleanField(default=False)
    deadline = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Date limite de candidature (optionnel).',
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_job_offers',
    )

    class Meta:
        db_table = 'jobs_joboffer'
        verbose_name = 'Offre d\'emploi'
        verbose_name_plural = 'Offres d\'emploi'
        unique_together = [['company', 'slug']]
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['status', 'published_at']),
            models.Index(fields=['country', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.company.name})'


class ScreeningRule(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Règle de pré-sélection : mots-clés CV, années d'exp. min, niveau d'études, etc. Pondération pour le scoring."""

    class RuleType(models.TextChoices):
        KEYWORDS = 'keywords', 'Mots-clés (CV)'
        MIN_EXPERIENCE = 'min_experience', 'Années d\'expérience min'
        EDUCATION_LEVEL = 'education_level', 'Niveau d\'études'
        LOCATION = 'location', 'Localisation'
        CUSTOM = 'custom', 'Personnalisé'

    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.CASCADE,
        related_name='screening_rules',
        db_index=True,
    )
    rule_type = models.CharField(max_length=30, choices=RuleType.choices, db_index=True)
    value = models.JSONField(
        default=dict,
        help_text='Ex: {"keywords": ["Python", "Django"]}, {"years": 3}, {"level": "master"}',
    )
    weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.0,
        help_text='Pondération pour le scoring (ex: 1.5 = règle prioritaire)',
    )
    is_required = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        db_table = 'jobs_screeningrule'
        verbose_name = 'Règle de screening'
        verbose_name_plural = 'Règles de screening'
        ordering = ['order', 'id']
        indexes = [
            models.Index(fields=['job_offer', 'order']),
        ]

    def __str__(self):
        return f'{self.get_rule_type_display()} pour {self.job_offer.title}'


class PreselectionSettings(TimeStampedMixin, models.Model):
    """Paramètres de présélection automatique par offre (aucun critère obligatoire à la création)."""
    job_offer = models.OneToOneField(
        JobOffer,
        on_delete=models.CASCADE,
        related_name='preselection_settings',
        primary_key=True,
    )
    criteria_json = models.JSONField(default=dict, blank=True)
    score_threshold = models.FloatField(default=60.0)
    max_candidates = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'jobs_preselectionsettings'
        verbose_name = 'Paramètres de présélection'
        verbose_name_plural = 'Paramètres de présélection'

    def __str__(self):
        return f'Présélection {self.job_offer.title}'


class SelectionSettings(TimeStampedMixin, models.Model):
    """Paramètres de sélection (shortlist) : seuil, max candidats, mode AUTO ou SEMI_AUTOMATIC, mode scoring (rule-based / hybride / ML)."""
    class SelectionMode(models.TextChoices):
        AUTO = 'auto', 'Automatique'
        SEMI_AUTOMATIC = 'semi_automatic', 'Semi-automatique'

    class ScoringMode(models.TextChoices):
        RULE_BASED = 'rule_based', 'Règles uniquement'
        HYBRID = 'hybrid', 'Hybride (règles + ML)'
        ML_ONLY = 'ml_only', 'ML uniquement'

    job_offer = models.OneToOneField(
        JobOffer,
        on_delete=models.CASCADE,
        related_name='selection_settings',
        primary_key=True,
    )
    criteria_json = models.JSONField(default=dict, blank=True)
    score_threshold = models.FloatField(default=60.0)
    max_candidates = models.PositiveIntegerField(null=True, blank=True)
    selection_mode = models.CharField(
        max_length=20,
        choices=SelectionMode.choices,
        default=SelectionMode.SEMI_AUTOMATIC,
        db_index=True,
    )
    scoring_mode = models.CharField(
        max_length=20,
        choices=ScoringMode.choices,
        default=ScoringMode.RULE_BASED,
        db_index=True,
        help_text='RULE_BASED: score règles ; HYBRID: combinaison règles + ML ; ML_ONLY: score ML seul.',
    )
    rule_based_weight = models.FloatField(
        default=0.6,
        help_text='Poids du score rule-based dans le mode HYBRID (final = rule*weight + ml*(1-weight)).',
    )
    ml_weight = models.FloatField(
        default=0.4,
        help_text='Poids du score ML dans le mode HYBRID.',
    )

    class Meta:
        db_table = 'jobs_selectionsettings'
        verbose_name = 'Paramètres de sélection'
        verbose_name_plural = 'Paramètres de sélection'

    def __str__(self):
        return f'Sélection {self.job_offer.title} ({self.get_selection_mode_display()})'
