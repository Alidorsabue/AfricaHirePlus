"""
Tests d'évaluation et questions (multi-tenant par company).
Résultats : CandidateTestResult lié à une Application.

Version durcie (P1–P5) :
- Token d'accès UNIQUE par candidat (TestAccessGrant) en plus de l'access_code partagé.
- Sessions horodatées avec client_ip (audit).
- Score "en attente review" et `is_passed` calculés.
- numeric_tolerance configurable par question.
- shuffle_questions / questions_per_session pour anti-triche.

P8c — Anonymisation des fichiers uploadés :
- `upload_to` UUID pour Answer.file et Question.attachment, afin que le nom
  original du fichier (qui peut contenir le nom du candidat, ex.
  "cv_jean_martin.pdf") ne soit jamais exposé au correcteur via file_url.
"""
import os
import secrets
import uuid

from django.core.validators import MinValueValidator
from django.db import models

from apps.companies.models import Company
from apps.core.models import SoftDeleteMixin, TimeStampedMixin
from apps.applications.models import Application
from apps.jobs.models import JobOffer


def _anonymized_answer_file_path(instance, filename: str) -> str:
    """
    Renomme un upload de réponse candidat en UUID pour empêcher toute fuite
    d'information identifiante via le nom de fichier (ex. 'cv_jean.pdf').

    Format : tests/answers/<year>/<month>/<session_id>/<uuid>.<ext>
    L'extension d'origine est conservée pour permettre l'ouverture
    correcte côté correcteur (Excel, PDF, etc.).
    """
    from django.utils import timezone as _tz
    ext = os.path.splitext(filename or '')[1].lower()
    safe_ext = ext if ext and len(ext) <= 8 else ''
    now = _tz.now()
    session_id = getattr(instance, 'session_id', 0) or 0
    return f"tests/answers/{now:%Y}/{now:%m}/{session_id}/{uuid.uuid4().hex}{safe_ext}"


def _anonymized_question_attachment_path(instance, filename: str) -> str:
    """Renomme les attachments de questions en UUID."""
    from django.utils import timezone as _tz
    ext = os.path.splitext(filename or '')[1].lower()
    safe_ext = ext if ext and len(ext) <= 8 else ''
    now = _tz.now()
    test_id = getattr(instance, 'test_id', 0) or 0
    return f"tests/questions/{now:%Y}/{now:%m}/{test_id}/{uuid.uuid4().hex}{safe_ext}"


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
        help_text=(
            "Code d'accès (token partagé) pour les candidats shortlistés de l'offre liée. "
            "P5 : préférer TestAccessGrant.token (un token unique par candidat)."
        ),
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # P5 — Anti-triche
    shuffle_questions = models.BooleanField(
        default=False,
        help_text="Si True, les questions sont présentées dans un ordre aléatoire propre à chaque candidat.",
    )
    shuffle_options = models.BooleanField(
        default=False,
        help_text="Si True, les options des QCM sont mélangées par candidat.",
    )
    questions_per_session = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text=(
            "Si défini, seul un sous-ensemble de N questions tirées aléatoirement "
            "(parmi toutes celles du test) est présenté à chaque candidat."
        ),
    )

    class Meta:
        db_table = 'tests_test'
        verbose_name = 'Test'
        verbose_name_plural = 'Tests'
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['job_offer', 'is_active']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'access_code'],
                condition=models.Q(access_code__gt=''),
                name='tests_test_access_code_unique_per_company',
            ),
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
    points = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Poids / score maximum pour la question. Doit être ≥ 1.',
    )
    numeric_tolerance = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            "Tolérance pour les questions numériques (proportion : 0.01 = ±1 %). "
            "Si None, valeur par défaut globale 1 %. 0 = égalité stricte."
        ),
    )
    order = models.PositiveSmallIntegerField(default=0, db_index=True)
    competencies = models.JSONField(
        default=list,
        blank=True,
        help_text='Tags de compétences, ex: ["Python", "Django"] pour scoring par compétence.',
    )
    attachment = models.FileField(
        upload_to=_anonymized_question_attachment_path,
        null=True,
        blank=True,
        help_text=(
            "Fichier ressource (énoncé détaillé, jeu de données, template, etc.). "
            "P8c — Stocké sous un nom UUID pour anonymisation."
        ),
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
    is_passed = models.BooleanField(
        null=True,
        blank=True,
        db_index=True,
        help_text='True si score >= test.passing_score (None tant que le scoring n\'est pas finalisé).',
    )
    pending_review_points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Points en attente de révision manuelle (open_text / code / file_upload).',
    )
    client_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Adresse IP vue lors de la session de test (pour audit).",
    )
    last_seen_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Dernière IP vue (auto-save / tab-switch) — détection de changement de réseau.",
    )
    question_order = models.JSONField(
        default=list,
        blank=True,
        help_text='Liste des IDs de questions présentées au candidat (P5 — shuffle / pool).',
    )
    # P8 — Anonymisation pour les correcteurs externes (rôle Correcteur)
    display_code = models.CharField(
        max_length=12,
        blank=True,
        db_index=True,
        help_text=(
            "Code d'affichage anonymisé (ex. 'C-A3F9B2C1') unique au sein du test. "
            "Présenté au correcteur à la place du nom du candidat. "
            "Généré paresseusement lors de la première vue correcteur."
        ),
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
            models.Index(fields=['is_passed']),
        ]

    def __str__(self):
        return f'{self.application.candidate.get_full_name()} - {self.test.title}: {self.score}/{self.max_score}'

    @property
    def company_id(self):
        return self.application.job_offer.company_id

    @property
    def is_finalized(self) -> bool:
        """True si la session est figée (soumise, notée ou expirée) — aucune modif acceptée."""
        return self.is_completed or self.status in (
            self.Status.SUBMITTED,
            self.Status.SCORED,
            self.Status.EXPIRED,
        )


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
        upload_to=_anonymized_answer_file_path,
        null=True,
        blank=True,
        help_text=(
            'Fichier réponse (Excel, Word, PDF, PowerPoint, PBIX, etc.). '
            'P8c — Stocké sous un nom UUID pour ne pas fuiter l\'identité '
            'du candidat (ex. "cv_jean.pdf") vers le correcteur externe.'
        ),
    )

    is_correct = models.BooleanField(
        null=True,
        blank=True,
        db_index=True,
        help_text='True si la réponse est correcte (None pour open_text/code/file en attente de review).',
    )
    pending_manual_review = models.BooleanField(
        default=False,
        db_index=True,
        help_text='True pour les types nécessitant une correction manuelle (texte libre, code, fichier).',
    )

    class Meta:
        db_table = 'tests_answer'
        verbose_name = 'Réponse à une question'
        verbose_name_plural = 'Réponses à des questions'
        unique_together = [['session', 'question']]
        indexes = [
            models.Index(fields=['session', 'question']),
            models.Index(fields=['pending_manual_review']),
        ]

    def __str__(self):
        return f'Answer q#{self.question_id} session#{self.session_id}'


# ---------------------------------------------------------------------------
# P5 — Anti-triche : token unique par candidat
# ---------------------------------------------------------------------------
def _generate_grant_token() -> str:
    """Token 32 octets URL-safe (~43 chars) — entropie suffisante pour bloquer le brute-force."""
    return secrets.token_urlsafe(32)


class TestAccessGrant(TimeStampedMixin, models.Model):
    """
    Token d'accès UNIQUE par candidat pour un test donné.

    Remplace progressivement `Test.access_code` qui est partagé entre tous les
    candidats. Permet :
      - de révoquer l'accès d'un seul candidat sans toucher les autres ;
      - de tracer qui a tenté d'utiliser quel token (audit) ;
      - de générer un lien personnel (sans demander email + code commun).
    """
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='access_grants',
        db_index=True,
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='test_access_grants',
        db_index=True,
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_grant_token,
        db_index=True,
    )
    is_revoked = models.BooleanField(default=False, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True, help_text="Date de la première utilisation.")
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'tests_testaccessgrant'
        verbose_name = "Token d'accès test"
        verbose_name_plural = "Tokens d'accès tests"
        unique_together = [['test', 'application']]
        indexes = [
            models.Index(fields=['token', 'is_revoked']),
            models.Index(fields=['application', 'is_revoked']),
        ]

    def __str__(self):
        return f'Grant#{self.id} test={self.test_id} app={self.application_id}'


# ---------------------------------------------------------------------------
# P8 — Correcteurs externes (sans compte plateforme)
# ---------------------------------------------------------------------------
def _generate_corrector_token() -> str:
    """Token 48 octets URL-safe (~64 chars) pour l'accès magique au correcteur."""
    return secrets.token_urlsafe(48)


class CorrectorAssignment(TimeStampedMixin, models.Model):
    """
    Désignation d'un correcteur externe pour corriger les soumissions d'un test.

    Le correcteur ne dispose PAS d'un compte plateforme : il accède aux
    soumissions via un lien magique contenant un token signé envoyé par email.

    Périmètre de visibilité :
      - `all_candidates = True` (défaut) : voit toutes les sessions SCORED du test.
      - `all_candidates = False` : voit uniquement les sessions des Applications
        listées dans `assigned_applications` (M2M).

    Le correcteur peut modifier le score de TOUTES les réponses (y compris les
    réponses automatiquement corrigées QCM / true_false / numeric).

    Anonymisation : le correcteur ne voit aucune info identifiante du candidat
    (nom, email, photo) — uniquement `display_code` du `CandidateTestResult`.
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='corrector_assignments',
        db_index=True,
        help_text='Entreprise propriétaire (multi-tenant).',
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name='corrector_assignments',
        db_index=True,
    )
    email = models.EmailField(
        db_index=True,
        help_text="Email du correcteur. C'est l'identité fonctionnelle.",
    )
    full_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nom optionnel pour personnaliser l'email d'invitation.",
    )
    token = models.CharField(
        max_length=96,
        unique=True,
        default=_generate_corrector_token,
        db_index=True,
        help_text='Token signé URL-safe pour authentification sans compte.',
    )
    all_candidates = models.BooleanField(
        default=True,
        help_text=(
            "Si True, le correcteur voit toutes les sessions SCORED de ce test "
            "(y compris les soumissions futures). Si False, restreint à "
            "assigned_applications."
        ),
    )
    assigned_applications = models.ManyToManyField(
        Application,
        blank=True,
        related_name='corrector_assignments',
        help_text=(
            "Candidatures explicitement attribuées (utilisé si "
            "all_candidates=False). Le correcteur ne verra QUE ces sessions."
        ),
    )
    assigned_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correctors_assigned',
        help_text='Recruteur ayant créé cette assignation.',
    )
    is_revoked = models.BooleanField(default=False, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='correctors_revoked',
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Date d\'expiration du token (None = pas d\'expiration).',
    )
    first_used_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    use_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'tests_correctorassignment'
        verbose_name = 'Assignation correcteur'
        verbose_name_plural = 'Assignations correcteurs'
        unique_together = [['test', 'email']]
        indexes = [
            models.Index(fields=['token', 'is_revoked']),
            models.Index(fields=['test', 'is_revoked']),
            models.Index(fields=['company', 'is_revoked']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        scope = 'all' if self.all_candidates else 'restricted'
        return f'Corrector {self.email} test#{self.test_id} ({scope})'

    @property
    def is_active(self) -> bool:
        from django.utils import timezone as _tz
        if self.is_revoked:
            return False
        if self.expires_at and self.expires_at < _tz.now():
            return False
        return True


# ---------------------------------------------------------------------------
# P6 — Audit / traçabilité des modifications de score (review manuelle)
# ---------------------------------------------------------------------------
class TestAuditLog(models.Model):
    """
    Journal d'audit : toute modification manuelle d'une réponse / d'un score
    (review d'un open_text par un recruteur, ajustement de points, etc.).

    Permet d'expliquer pourquoi un score a changé entre la soumission auto et
    le résultat final affiché au candidat.
    """
    class Action(models.TextChoices):
        SCORE_OVERRIDE = 'score_override', 'Modification manuelle du score'
        MANUAL_REVIEW = 'manual_review', "Notation d'une question en attente"
        STATUS_CHANGE = 'status_change', 'Changement de statut'
        FLAG_TOGGLED = 'flag_toggled', 'Modification du flag (suspect / OK)'
        ACCESS_REVOKED = 'access_revoked', "Révocation d'un token d'accès"
        # P8 — Correcteurs externes
        CORRECTOR_ASSIGNED = 'corrector_assigned', "Assignation d'un correcteur"
        CORRECTOR_REVOKED = 'corrector_revoked', "Révocation d'un correcteur"
        CORRECTOR_REVIEW = 'corrector_review', "Notation par un correcteur externe"

    session = models.ForeignKey(
        CandidateTestResult,
        on_delete=models.CASCADE,
        related_name='audit_log',
        db_index=True,
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_log',
        help_text='Réponse concernée (si applicable).',
    )
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    actor = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_audit_entries',
        help_text='Utilisateur qui a effectué l\'action (recruteur, admin).',
    )
    # P8 — Acteur alternatif : un correcteur externe (sans compte plateforme)
    corrector = models.ForeignKey(
        'tests.CorrectorAssignment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_entries',
        help_text="Acteur correcteur externe (si l'action a été faite via un token correcteur).",
    )
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tests_testauditlog'
        verbose_name = "Entrée d'audit test"
        verbose_name_plural = "Journal d'audit tests"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'action']),
            models.Index(fields=['actor', 'created_at']),
            models.Index(fields=['corrector', 'created_at']),
        ]

    def __str__(self):
        who = self.actor_id or f'corrector#{self.corrector_id}' or '?'
        return f'{self.action} session#{self.session_id} by {who}'
