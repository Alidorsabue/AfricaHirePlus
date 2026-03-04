"""
Tests d'évaluation et questions (multi-tenant par company).
Résultats : CandidateTestResult lié à une Application.
"""
from django.db import models

from apps.companies.models import Company
from apps.core.models import SoftDeleteMixin, TimeStampedMixin
from apps.applications.models import Application
from apps.jobs.models import JobOffer


class Test(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Test / quiz d'évaluation (technique, comportemental, etc.)."""

    class TestType(models.TextChoices):
        TECHNICAL = 'technical', 'Technique'
        PERSONALITY = 'personality', 'Personnalité'
        LANGUAGE = 'language', 'Langue'
        CASE_STUDY = 'case_study', 'Étude de cas'
        OTHER = 'other', 'Autre'

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='tests',
        db_index=True,
    )
    job_offer = models.ForeignKey(
        JobOffer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tests',
        db_index=True,
        help_text="Offre concernée par ce test (pour restreindre l'accès aux candidats shortlistés).",
    )
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    test_type = models.CharField(
        max_length=20,
        choices=TestType.choices,
        default=TestType.TECHNICAL,
        db_index=True,
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    total_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Score total (somme des points des questions), recalculé automatiquement.',
    )
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Score minimum pour valider (ex: 60.00)',
    )
    access_code = models.CharField(
        max_length=32,
        blank=True,
        help_text="Code d'accès (token partagé) pour les candidats shortlistés de l'offre liée.",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'tests_test'
        verbose_name = 'Test'
        verbose_name_plural = 'Tests'
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['job_offer', 'is_active']),
        ]

    def __str__(self):
        return f'{self.title} ({self.company.name})'


class Section(TimeStampedMixin, models.Model):
    """
    Section d'un test (regroupement logique de questions).
    Utilisée pour le scoring par section dans les rapports.
    """

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='sections',
        db_index=True,
    )
    title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0, db_index=True)

    class Meta:
        db_table = 'tests_section'
        verbose_name = 'Section de test'
        verbose_name_plural = 'Sections de test'
        ordering = ['test', 'order', 'id']
        indexes = [
            models.Index(fields=['test', 'order']),
        ]

    def __str__(self):
        return f'{self.title} ({self.test.title})'


class Question(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Question d'un test."""

    class QuestionType(models.TextChoices):
        # Nouveau schéma (iMocha-like)
        QCM_SINGLE = 'qcm_single', 'QCM (choix unique)'
        QCM_MULTI = 'qcm_multi', 'QCM (choix multiples)'
        TRUE_FALSE = 'true_false', 'Vrai / Faux'
        NUMERIC = 'numeric', 'Numérique'
        OPEN_TEXT = 'open_text', 'Texte libre'
        FILE_UPLOAD = 'file_upload', 'Upload de fichier'
        CODE = 'code', 'Question de code'
        # Legacy (compatibilité avec données existantes)
        SINGLE_CHOICE = 'single_choice', 'Choix unique'
        MULTIPLE_CHOICE = 'multiple_choice', 'Choix multiples'
        TEXT = 'text', 'Texte libre'
        NUMBER = 'number', 'Numérique'
        BOOLEAN = 'boolean', 'Oui/Non'

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='questions',
        db_index=True,
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='questions',
        null=True,
        blank=True,
        db_index=True,
    )
    section_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nom de section (fallback si section FK non utilisée).",
    )
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True,
    )
    text = models.TextField()
    options = models.JSONField(
        default=list,
        blank=True,
        help_text='Pour QCM: [{"id": "a", "label": "Option A", "correct": true}]',
    )
    correct_answer = models.JSONField(
        null=True,
        blank=True,
        help_text='Réponse attendue (texte, nombre, ou liste d\'ids pour QCM)',
    )
    points = models.PositiveSmallIntegerField(default=1, help_text='Poids / score maximum pour la question.')
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    competencies = models.JSONField(
        default=list,
        blank=True,
        help_text='Tags de compétences, ex: ["Python", "Django"] pour scoring par compétence.',
    )
    attachment = models.FileField(
        upload_to='tests/questions/%Y/%m/',
        null=True,
        blank=True,
        help_text="Fichier ressource (énoncé détaillé, jeu de données, template, etc.).",
    )
    code_language = models.CharField(
        max_length=50,
        blank=True,
        help_text="Langage attendu pour une question de type code (ex: python, javascript).",
    )
    starter_code = models.TextField(
        blank=True,
        help_text="Code de départ facultatif pour les questions de code.",
    )

    class Meta:
        db_table = 'tests_question'
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'
        ordering = ['test', 'order', 'id']
        indexes = [
            models.Index(fields=['test', 'order']),
            models.Index(fields=['section', 'order']),
        ]

    def __str__(self):
        return f'{self.text[:50]}...' if len(self.text) > 50 else self.text


class CandidateTestResult(TimeStampedMixin, models.Model):
    """Résultat d'un candidat à un test (lié à une candidature)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        IN_PROGRESS = 'in_progress', 'En cours'
        SUBMITTED = 'submitted', 'Soumis'
        SCORED = 'scored', 'Noté'
        EXPIRED = 'expired', 'Expiré'

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='test_results',
        db_index=True,
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='candidate_results',
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    answers = models.JSONField(
        default=dict,
        blank=True,
        help_text='Réponses: { "question_id": "answer" ou ["id1", "id2"] }',
    )
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    tab_switch_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Nombre de changements d'onglet détectés côté client pendant le test.",
    )
    is_flagged = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Marqué comme suspect si tab_switch_count dépasse le seuil.',
    )
    is_completed = models.BooleanField(
        default=False,
        db_index=True,
        help_text='Test terminé (soumis ou expiré).',
    )
    client_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Adresse IP vue lors de la session de test (pour audit).",
    )

    class Meta:
        db_table = 'tests_candidatetestresult'
        verbose_name = 'Résultat de test candidat'
        verbose_name_plural = 'Résultats de tests candidats'
        unique_together = [['application', 'test']]
        indexes = [
            models.Index(fields=['application', 'status']),
            models.Index(fields=['test', 'status']),
            models.Index(fields=['is_flagged']),
        ]

    def __str__(self):
        return f'{self.application.candidate.get_full_name()} - {self.test.title}: {self.score}/{self.max_score}'

    @property
    def company_id(self):
        return self.application.job_offer.company_id


class Answer(TimeStampedMixin, models.Model):
    """
    Réponse individuelle à une question dans le cadre d'une session de test.
    Permet une traçabilité fine par question (utile pour les rapports détaillés / export PDF).
    """

    session = models.ForeignKey(
        CandidateTestResult,
        on_delete=models.CASCADE,
        related_name='answer_rows',
        db_index=True,
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        db_index=True,
    )
    response = models.JSONField(
        null=True,
        blank=True,
        help_text='Réponse brute du candidat pour cette question (texte, JSON, code, méta fichier).',
    )
    score_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Score obtenu pour cette question (0 à points).',
    )
    file = models.FileField(
        upload_to='tests/answers/%Y/%m/',
        null=True,
        blank=True,
        help_text='Fichier réponse (Excel, Word, PDF, PowerPoint, PBIX, etc.) pour les questions file_upload.',
    )

    class Meta:
        db_table = 'tests_answer'
        verbose_name = 'Réponse à une question'
        verbose_name_plural = 'Réponses à des questions'
        unique_together = [['session', 'question']]
        indexes = [
            models.Index(fields=['session', 'question']),
        ]

    def __str__(self):
        return f'Answer q#{self.question_id} session#{self.session_id}'
