"""
Serializers du module Tests (évaluations candidats).

Deux familles de serializers :
- Recruteur / Admin (RH) : voient correct_answer, access_code, etc.
- Candidat : reçoivent un payload assaini — JAMAIS correct_answer, JAMAIS
  l'indicateur `correct: true` dans les options, JAMAIS access_code.

Toute exposition de la bonne réponse à un candidat est une faille critique.
Voir docs/TESTS_MODULE_HARDENING.md (P1).
"""
from rest_framework import serializers

from .models import Answer, CandidateTestResult, CorrectorAssignment, Question, Section, Test


# ---------------------------------------------------------------------------
# RECRUTEUR / ADMIN — vue complète (avec correct_answer)
# ---------------------------------------------------------------------------
class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'title', 'order']
        read_only_fields = ['id']


class QuestionSerializer(serializers.ModelSerializer):
    """Vue RECRUTEUR : expose correct_answer + flag `correct` dans les options."""
    section_title = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'section',
            'section_title',
            'question_type',
            'text',
            'options',
            'correct_answer',
            'points',
            'order',
            'attachment',
            'code_language',
            'starter_code',
            'competencies',
        ]
        read_only_fields = ['id', 'attachment']

    def get_section_title(self, obj):
        if obj.section_id:
            return obj.section.title if hasattr(obj, 'section') and obj.section else ''
        return getattr(obj, 'section_title', '') or ''


# ---------------------------------------------------------------------------
# CANDIDAT — vue assainie (JAMAIS de correct_answer)
# ---------------------------------------------------------------------------
def _strip_correct_flag_from_options(options):
    """
    Retire le flag `correct` (et toute clé suspecte) de chaque option avant
    transmission au candidat. Cette fonction est le SEUL point de filtrage —
    toute modification doit être croisée avec les tests P7.
    """
    if not isinstance(options, list):
        return []
    safe_keys = {'id', 'label', 'value', 'image', 'attachment_url'}
    cleaned = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        cleaned.append({k: v for k, v in opt.items() if k in safe_keys})
    return cleaned


class CandidateQuestionSerializer(serializers.ModelSerializer):
    """
    Vue CANDIDAT : strictement épurée des réponses correctes.
    - `correct_answer` JAMAIS sérialisé.
    - `options` filtrées : `correct` retiré de chaque option.
    - `section_title` exposé pour navigation seulement.
    """
    section_title = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'section',
            'section_title',
            'question_type',
            'text',
            'options',
            'points',
            'order',
            'attachment',
            'code_language',
            'starter_code',
        ]
        read_only_fields = fields

    def get_section_title(self, obj):
        if obj.section_id:
            return obj.section.title if hasattr(obj, 'section') and obj.section else ''
        return getattr(obj, 'section_title', '') or ''

    def get_options(self, obj):
        return _strip_correct_flag_from_options(obj.options or [])


class CandidateTestSerializer(serializers.ModelSerializer):
    """
    Vue CANDIDAT du Test : sans access_code, sans passing_score (info RH),
    questions servies par `CandidateQuestionSerializer`.
    """
    questions = CandidateQuestionSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = [
            'id', 'job_offer', 'title', 'description', 'test_type',
            'duration_minutes', 'is_active',
            'sections', 'questions',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# WRITE — création / édition (recruteur / admin)
# ---------------------------------------------------------------------------
class QuestionWriteSerializer(serializers.ModelSerializer):
    """Création/édition de questions. section_index = index dans la liste sections (0-based)."""
    section_index = serializers.IntegerField(required=False, allow_null=True)
    numeric_tolerance = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0,
        help_text='Tolérance en pourcentage (0.01 = 1 %). Par défaut 1 %. Voir P2.',
    )

    class Meta:
        model = Question
        fields = [
            'id',
            'question_type',
            'text',
            'options',
            'correct_answer',
            'points',
            'order',
            'code_language',
            'starter_code',
            'competencies',
            'section_index',
            'numeric_tolerance',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'text': {'required': True},
            'points': {'min_value': 1},
        }

    def validate(self, attrs):
        """
        Validation P3 : cohérence type ↔ options ↔ correct_answer.

        Garantit qu'on ne peut pas créer de question piégée (toutes les réponses
        valent 0 par erreur de saisie).
        """
        qtype = attrs.get('question_type') or (self.instance.question_type if self.instance else None)
        options = attrs.get('options', self.instance.options if self.instance else [])
        correct = attrs.get('correct_answer', self.instance.correct_answer if self.instance else None)

        qcm_single = {Question.QuestionType.QCM_SINGLE, Question.QuestionType.SINGLE_CHOICE}
        qcm_multi = {Question.QuestionType.QCM_MULTI, Question.QuestionType.MULTIPLE_CHOICE}
        true_false = {Question.QuestionType.TRUE_FALSE, Question.QuestionType.BOOLEAN}
        numeric = {Question.QuestionType.NUMERIC, Question.QuestionType.NUMBER}

        if qtype in (qcm_single | qcm_multi):
            if not options or not isinstance(options, list):
                raise serializers.ValidationError(
                    {'options': 'Une question QCM doit fournir au moins 2 options.'}
                )
            if len(options) < 2:
                raise serializers.ValidationError(
                    {'options': 'Au moins 2 options sont requises pour un QCM.'}
                )
            ids = [str(o.get('id') or '').strip() for o in options if isinstance(o, dict)]
            if len(set(ids)) != len(ids):
                raise serializers.ValidationError(
                    {'options': 'Les identifiants d\'options doivent être uniques.'}
                )
            correct_marked = [o for o in options if isinstance(o, dict) and o.get('correct')]
            if not correct_marked and not correct:
                raise serializers.ValidationError({
                    'correct_answer': (
                        'Aucune option marquée correcte et aucun correct_answer fourni. '
                        'La question serait toujours notée 0.'
                    )
                })
            if qtype in qcm_single and len(correct_marked) > 1:
                raise serializers.ValidationError({
                    'options': 'QCM choix unique : une seule option peut être correcte.'
                })

        if qtype in true_false and correct is None:
            raise serializers.ValidationError({
                'correct_answer': 'Question Vrai/Faux : correct_answer requis (true/false).'
            })

        if qtype in numeric:
            if correct is None:
                raise serializers.ValidationError({
                    'correct_answer': 'Question numérique : correct_answer (nombre attendu) requis.'
                })
            try:
                float(correct)
            except (TypeError, ValueError):
                raise serializers.ValidationError({
                    'correct_answer': 'correct_answer doit être un nombre pour une question numérique.'
                })
            tol = attrs.get('numeric_tolerance')
            if tol is not None and tol < 0:
                raise serializers.ValidationError({
                    'numeric_tolerance': 'La tolérance doit être positive.'
                })

        return attrs


class SectionWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField(default=0, min_value=0)


class TestSerializer(serializers.ModelSerializer):
    """Vue recruteur (READ) avec questions complètes."""
    questions = QuestionSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = [
            'id', 'company', 'job_offer', 'title', 'description', 'test_type',
            'duration_minutes', 'total_score', 'passing_score', 'access_code',
            'is_active', 'sections', 'questions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'access_code', 'total_score']


class TestWriteSerializer(serializers.ModelSerializer):
    """Création/édition Test avec sections et questions nested."""
    sections = SectionWriteSerializer(many=True, required=False)
    questions = QuestionWriteSerializer(many=True, required=False)

    class Meta:
        model = Test
        fields = [
            'id', 'job_offer', 'title', 'description', 'test_type',
            'duration_minutes', 'passing_score', 'is_active',
            'sections', 'questions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'duration_minutes': {'min_value': 1, 'required': False, 'allow_null': True},
        }

    def validate(self, attrs):
        passing = attrs.get('passing_score')
        if passing is not None and passing < 0:
            raise serializers.ValidationError({'passing_score': 'Doit être positif.'})
        return attrs

    def _persist_questions(self, instance, sections_data, questions_data):
        """Logique partagée create/update : remplace sections+questions."""
        instance.sections.all().delete()
        created_sections = []
        for s in sorted(sections_data or [], key=lambda x: x.get('order', 0)):
            sec = Section.objects.create(
                test=instance, title=s['title'],
                order=s.get('order', len(created_sections)),
            )
            created_sections.append(sec)

        if questions_data is not None:
            # Hard delete pour éviter d'accumuler des soft-deleted invisibles
            Question.objects.filter(test=instance).delete()
            for q in questions_data:
                q = dict(q)
                section_index = q.pop('section_index', None)
                q.pop('id', None)
                section_id = None
                if section_index is not None and 0 <= section_index < len(created_sections):
                    section_id = created_sections[section_index].id
                Question.objects.create(test=instance, section_id=section_id, **q)

    def create(self, validated_data):
        sections_data = validated_data.pop('sections', [])
        questions_data = validated_data.pop('questions', [])
        instance = Test.objects.create(**validated_data)
        self._persist_questions(instance, sections_data, questions_data)
        # Recalcul total_score (P2)
        from .services import recompute_test_total_score
        recompute_test_total_score(instance)
        return instance

    def update(self, instance, validated_data):
        sections_data = validated_data.pop('sections', None)
        questions_data = validated_data.pop('questions', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if sections_data is not None or questions_data is not None:
            self._persist_questions(instance, sections_data, questions_data)
        from .services import recompute_test_total_score
        recompute_test_total_score(instance)
        return instance


# ---------------------------------------------------------------------------
# Résultats
# ---------------------------------------------------------------------------
class CandidateTestResultSerializer(serializers.ModelSerializer):
    is_passed = serializers.SerializerMethodField()
    pending_review_points = serializers.SerializerMethodField()

    class Meta:
        model = CandidateTestResult
        fields = [
            'id', 'application', 'test', 'status', 'score', 'max_score',
            'is_passed', 'pending_review_points',
            'answers', 'started_at', 'submitted_at',
            'tab_switch_count', 'is_flagged', 'is_completed',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_passed(self, obj):
        return getattr(obj, 'is_passed', None)

    def get_pending_review_points(self, obj):
        return getattr(obj, 'pending_review_points', None)


class SubmitTestAnswersSerializer(serializers.Serializer):
    """Soumission des réponses à un test (answers = { question_id: value })."""
    application_id = serializers.IntegerField()
    test_id = serializers.IntegerField()
    answers = serializers.JSONField(help_text='{"1": "a", "2": ["a","b"]}')


# ===========================================================================
# P8 — CORRECTEUR EXTERNE
# ===========================================================================
#
# Trois familles de serializers :
#   - Recruteur : `CorrectorAssignmentSerializer` (lecture/CRUD).
#   - Correcteur (anonymisé) :
#       * `CorrectorSessionListSerializer` : liste des sessions à corriger.
#       * `CorrectorSessionDetailSerializer` : détail d'une session (questions
#         + réponses, avec correct_answer car ils doivent noter).
#       * `CorrectorAnswerSerializer` : ligne réponse anonyme.
#   - Tous les serializers correcteur sont READ-ONLY pour les infos candidat :
#       JAMAIS de email/nom/photo/téléphone, UNIQUEMENT `display_code`.


class CorrectorAssignmentReadSerializer(serializers.ModelSerializer):
    """Vue recruteur (lecture) — expose l'email mais pas le token complet."""
    assigned_application_ids = serializers.SerializerMethodField()
    token_preview = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = CorrectorAssignment
        fields = [
            'id', 'test', 'email', 'full_name',
            'all_candidates', 'assigned_application_ids',
            'token_preview',
            'is_revoked', 'revoked_at',
            'expires_at', 'first_used_at', 'last_used_at', 'use_count',
            'is_active', 'created_at',
        ]
        read_only_fields = fields

    def get_assigned_application_ids(self, obj):
        return list(obj.assigned_applications.values_list('id', flat=True))

    def get_token_preview(self, obj):
        """Aperçu des 4 premiers caractères, jamais le token complet."""
        if not obj.token:
            return ''
        return obj.token[:4] + '…'


class CorrectorAssignmentWriteSerializer(serializers.Serializer):
    """
    Création / mise à jour d'une assignation correcteur par un recruteur.

    Champs :
      - email (requis) : l'email du correcteur.
      - full_name (optionnel) : pour personnaliser le mail.
      - assigned_application_ids (optionnel) : si présent, restreint le
        correcteur à ces candidatures. Si absent ou null, le correcteur voit
        toutes les sessions du test.
      - expires_in_days (optionnel, défaut 30).
    """
    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    assigned_application_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_null=True,
        allow_empty=True,
        help_text=(
            "Si fourni (même liste vide), restreint le correcteur à ces "
            "candidatures. Si null/absent, le correcteur voit toutes les sessions."
        ),
    )
    expires_in_days = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=365,
        default=30,
    )


# --- Vues anonymisées pour le correcteur -------------------------------------
class CorrectorAnswerSerializer(serializers.ModelSerializer):
    """
    Représentation d'une réponse vue par le correcteur.
    - Pas d'info candidat.
    - Aucun champ qui pourrait identifier le candidat (file URL contient des
      info uniquement liées au test).
    """
    question_id = serializers.IntegerField(source='question.id', read_only=True)
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    question_points = serializers.IntegerField(source='question.points', read_only=True)
    question_options = serializers.JSONField(source='question.options', read_only=True)
    question_correct_answer = serializers.JSONField(source='question.correct_answer', read_only=True)
    question_section_title = serializers.SerializerMethodField()
    question_competencies = serializers.JSONField(source='question.competencies', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = [
            'id',
            'question_id', 'question_text', 'question_type',
            'question_points', 'question_options', 'question_correct_answer',
            'question_section_title', 'question_competencies',
            'response',
            'score_obtained', 'is_correct', 'pending_manual_review',
            'file_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_question_section_title(self, obj):
        q = obj.question
        if q.section_id and q.section:
            return q.section.title or ''
        return q.section_title or ''

    def get_file_url(self, obj):
        if not obj.file:
            return None
        try:
            return obj.file.url
        except Exception:
            return None


class CorrectorSessionListSerializer(serializers.ModelSerializer):
    """
    Liste des sessions à corriger — UNIQUEMENT le code anonymisé + métadonnées
    de scoring. AUCUNE info candidat n'est sérialisée.
    """
    display_code = serializers.CharField(read_only=True)
    pending_answers_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CandidateTestResult
        fields = [
            'id', 'display_code', 'status',
            'score', 'max_score', 'pending_review_points',
            'is_passed', 'is_flagged', 'submitted_at',
            'pending_answers_count',
        ]
        read_only_fields = fields


class CorrectorTestInfoSerializer(serializers.ModelSerializer):
    """Infos test pour le correcteur (titre, description, job role)."""
    job_role = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            'id', 'title', 'description', 'test_type',
            'duration_minutes', 'total_score', 'passing_score',
            'job_role',
        ]
        read_only_fields = fields

    def get_job_role(self, obj):
        """Titre de l'offre d'emploi associée (sans nom de candidat ni info company)."""
        if obj.job_offer_id and obj.job_offer:
            return obj.job_offer.title
        return ''


class CorrectorSessionDetailSerializer(serializers.ModelSerializer):
    """
    Détail anonymisé d'une session pour le correcteur.
    Contient TOUT ce qu'il faut pour noter :
      - infos test (titre, description, job role, passing_score)
      - toutes les réponses (avec question, correct_answer, options)
      - aucune donnée identifiante.
    """
    display_code = serializers.CharField(read_only=True)
    test_info = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()

    class Meta:
        model = CandidateTestResult
        fields = [
            'id', 'display_code', 'status',
            'score', 'max_score', 'pending_review_points',
            'is_passed', 'is_flagged', 'tab_switch_count',
            'started_at', 'submitted_at',
            'test_info', 'answers',
        ]
        read_only_fields = fields

    def get_test_info(self, obj):
        return CorrectorTestInfoSerializer(obj.test).data

    def get_answers(self, obj):
        rows = (
            obj.answer_rows
            .select_related('question', 'question__section')
            .order_by('question__order', 'question__id')
        )
        return CorrectorAnswerSerializer(rows, many=True).data


class CorrectorReviewSerializer(serializers.Serializer):
    """
    Soumission d'une notation par le correcteur.

    `score` est obligatoire ; `is_correct` optionnel (par défaut déduit du score).
    `reason` est libre — toujours stocké dans l'audit log pour traçabilité.
    """
    score = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=0)
    is_correct = serializers.BooleanField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
