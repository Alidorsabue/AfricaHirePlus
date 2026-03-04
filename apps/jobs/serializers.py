"""
Sérialiseurs offres d'emploi et règles de screening : lecture, écriture, liste, version publique.
"""
import json
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from .models import JobOffer, PreselectionSettings, ScreeningRule, SelectionSettings
from .scoring_engine import validate_criteria_json
from apps.applications.models import Application
from apps.candidates.serializers import CandidateListSerializer


def _validate_description_or_document(attrs, instance=None, request=None):
    """Valide qu'au moins une description (texte) ou un document (PDF/Word) est fourni."""
    has_desc = bool((attrs.get('description') or '').strip())
    has_doc = attrs.get('description_document') is not None
    if request and not has_doc and request.FILES.get('description_document'):
        has_doc = True
    if instance:
        has_desc = has_desc or bool((instance.description or '').strip())
        has_doc = has_doc or bool(instance.description_document)
    if not has_desc and not has_doc:
        raise serializers.ValidationError(
            {'description': 'Renseignez une description ou importez un document (PDF/Word).'}
        )
    return attrs


class ScreeningRuleSerializer(serializers.ModelSerializer):
    """Lecture des règles de screening (type, value, weight, is_required, order)."""
    class Meta:
        model = ScreeningRule
        fields = ['id', 'rule_type', 'value', 'weight', 'is_required', 'order']


class ScreeningRuleWriteSerializer(serializers.ModelSerializer):
    """Écriture des règles de screening (création/mise à jour)."""
    class Meta:
        model = ScreeningRule
        fields = ['id', 'rule_type', 'value', 'weight', 'is_required', 'order']


def _get_preselection_settings_obj(obj):
    return getattr(obj, 'preselection_settings', None) or PreselectionSettings.objects.filter(job_offer=obj).first()


def _get_selection_settings_obj(obj):
    return getattr(obj, 'selection_settings', None) or SelectionSettings.objects.filter(job_offer=obj).first()


class JobOfferSerializer(serializers.ModelSerializer):
    """Sérialiseur complet offre : champs + règles de screening + URL document + paramètres présélection/sélection + critères suggérés (JD)."""
    screening_rules = ScreeningRuleSerializer(many=True, read_only=True)
    description_document_url = serializers.SerializerMethodField(read_only=True)
    selection_mode = serializers.SerializerMethodField(read_only=True)
    preselection_settings = serializers.SerializerMethodField(read_only=True)
    selection_settings = serializers.SerializerMethodField(read_only=True)
    suggested_criteria = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobOffer
        fields = [
            'id', 'company', 'title', 'slug', 'description', 'description_document',
            'description_document_url', 'requirements', 'benefits',
            'location', 'country', 'contract_type', 'status', 'deadline',
            'salary_min', 'salary_max', 'salary_currency', 'salary_visible',
            'published_at', 'closed_at', 'created_by',
            'screening_rules', 'selection_mode', 'preselection_settings', 'selection_settings',
            'suggested_criteria',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'closed_at', 'created_at', 'updated_at']
        extra_kwargs = {'company': {'required': False}}

    def get_description_document_url(self, obj):
        if not obj.description_document:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.description_document.url)
        return obj.description_document.url

    def get_selection_mode(self, obj):
        settings = _get_selection_settings_obj(obj)
        return settings.selection_mode if settings else SelectionSettings.SelectionMode.SEMI_AUTOMATIC

    def get_preselection_settings(self, obj):
        settings = _get_preselection_settings_obj(obj)
        if not settings:
            return {'score_threshold': 60.0, 'max_candidates': None, 'criteria_json': {}}
        return {
            'score_threshold': float(settings.score_threshold),
            'max_candidates': settings.max_candidates,
            'criteria_json': settings.criteria_json or {},
        }

    def get_suggested_criteria(self, obj):
        """Critères identifiés à partir de l'offre (exigences en priorité) : mots-clés, expérience min, niveau d'études."""
        try:
            from ml.jd_keywords import extract_suggested_criteria
            return extract_suggested_criteria(obj)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "get_suggested_criteria failed for job id=%s: %s", getattr(obj, 'id', None), e
            )
            return {'keywords': [], 'min_experience': None, 'education_level': None}

    def get_selection_settings(self, obj):
        settings = _get_selection_settings_obj(obj)
        if not settings:
            return self._default_selection_settings()
        criteria = settings.criteria_json or {}
        selection_rules = (
            criteria.get('selection_rules') if isinstance(criteria, dict) else []
        )
        if not isinstance(selection_rules, list):
            selection_rules = []
        return {
            'score_threshold': float(settings.score_threshold),
            'max_candidates': settings.max_candidates,
            'selection_mode': settings.selection_mode,
            'scoring_mode': settings.scoring_mode,
            'rule_based_weight': float(settings.rule_based_weight),
            'ml_weight': float(settings.ml_weight),
            'criteria_json': criteria if isinstance(criteria, dict) else {},
            'selection_rules': selection_rules,
        }

    def _default_selection_settings(self):
        return {
            'score_threshold': 60.0,
            'max_candidates': None,
            'selection_mode': SelectionSettings.SelectionMode.SEMI_AUTOMATIC,
            'scoring_mode': SelectionSettings.ScoringMode.RULE_BASED,
            'rule_based_weight': 0.6,
            'ml_weight': 0.4,
            'criteria_json': {},
            'selection_rules': [],
        }

    def validate(self, attrs):
        # FormData peut envoyer des chaînes vides pour les champs numériques optionnels
        if attrs.get('salary_min') == '':
            attrs['salary_min'] = None
        if attrs.get('salary_max') == '':
            attrs['salary_max'] = None
        return _validate_description_or_document(
            attrs, instance=self.instance, request=self.context.get('request')
        )

    def _parse_screening_rules(self, request):
        """Retourne la liste des règles (depuis request.data, JSON ou FormData)."""
        if not request:
            return None
        data = request.data.get('screening_rules')
        if data is None:
            return None
        if isinstance(data, str) and data.strip():
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                return None
        return data if isinstance(data, list) else None

    def _apply_preselection_settings(self, instance, request):
        if not request:
            return
        data = request.data.get('preselection_settings')
        if isinstance(data, str) and data.strip():
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                return
        if not isinstance(data, dict):
            return
        settings, _ = PreselectionSettings.objects.get_or_create(
            job_offer=instance,
            defaults={'score_threshold': 60.0},
        )
        if 'score_threshold' in data and data['score_threshold'] is not None:
            settings.score_threshold = float(data['score_threshold'])
        if 'max_candidates' in data:
            settings.max_candidates = data['max_candidates'] if data['max_candidates'] else None
        if 'criteria_json' in data and data['criteria_json'] is not None:
            try:
                validate_criteria_json(data['criteria_json'])
                settings.criteria_json = data['criteria_json']
            except ValueError as e:
                raise serializers.ValidationError({'preselection_settings': {'criteria_json': str(e)}})
        settings.save(update_fields=['score_threshold', 'max_candidates', 'criteria_json', 'updated_at'])

    def _apply_selection_settings(self, instance, request):
        if not request:
            return
        data = request.data.get('selection_settings')
        if isinstance(data, str) and data.strip():
            try:
                data = json.loads(data)
            except (ValueError, TypeError):
                return
        if not isinstance(data, dict):
            data = {}
        selection_mode = request.data.get('selection_mode') or (data.get('selection_mode') if isinstance(data, dict) else None)
        settings, _ = SelectionSettings.objects.get_or_create(
            job_offer=instance,
            defaults={
                'selection_mode': SelectionSettings.SelectionMode.SEMI_AUTOMATIC,
                'scoring_mode': SelectionSettings.ScoringMode.RULE_BASED,
            },
        )
        if selection_mode and selection_mode in {c[0] for c in SelectionSettings.SelectionMode.choices}:
            settings.selection_mode = selection_mode
        if isinstance(data, dict):
            if 'score_threshold' in data and data['score_threshold'] is not None:
                settings.score_threshold = float(data['score_threshold'])
            if 'max_candidates' in data:
                settings.max_candidates = data['max_candidates'] if data['max_candidates'] else None
            if 'scoring_mode' in data and data['scoring_mode'] in {c[0] for c in SelectionSettings.ScoringMode.choices}:
                settings.scoring_mode = data['scoring_mode']
            if 'rule_based_weight' in data and data['rule_based_weight'] is not None:
                try:
                    settings.rule_based_weight = float(data['rule_based_weight'])
                except (TypeError, ValueError):
                    pass
            if 'ml_weight' in data and data['ml_weight'] is not None:
                try:
                    settings.ml_weight = float(data['ml_weight'])
                except (TypeError, ValueError):
                    pass
            if 'criteria_json' in data and data['criteria_json'] is not None:
                try:
                    validate_criteria_json(data['criteria_json'])
                    settings.criteria_json = data['criteria_json']
                except ValueError as e:
                    raise serializers.ValidationError({'selection_settings': {'criteria_json': str(e)}})
            elif 'selection_rules' in data:
                rules = data['selection_rules']
                if isinstance(rules, list):
                    criteria = dict(settings.criteria_json) if isinstance(settings.criteria_json, dict) else {}
                    criteria['selection_rules'] = rules
                    settings.criteria_json = criteria
        settings.save(update_fields=[
                'score_threshold', 'max_candidates', 'selection_mode',
                'scoring_mode', 'rule_based_weight', 'ml_weight',
                'criteria_json', 'updated_at',
            ])

    def _set_published_at_if_needed(self, validated_data, instance=None):
        """Si statut PUBLISHED et published_at non renseigné, mettre now()."""
        if validated_data.get('status') != JobOffer.Status.PUBLISHED:
            return
        if validated_data.get('published_at') is not None:
            return
        if instance and getattr(instance, 'published_at', None) is not None:
            return
        validated_data['published_at'] = timezone.now()

    def create(self, validated_data):
        self._set_published_at_if_needed(validated_data)
        if not validated_data.get('slug'):
            base = slugify(validated_data.get('title', ''))[:120] or 'offre'
            company = validated_data.get('company')
            company_id = validated_data.get('company_id')
            if company is None and company_id is not None:
                company = company_id  # pour la requête filter (accepte id ou instance)
            slug = base
            n = 0
            while company is not None and JobOffer.objects.filter(company=company, slug=slug).exists():
                n += 1
                slug = f'{base}-{n}'[:120]
            validated_data['slug'] = slug
        request = self.context.get('request')
        rules_data = self._parse_screening_rules(request)
        instance = super().create(validated_data)
        if rules_data:
            for r in rules_data:
                ser = ScreeningRuleWriteSerializer(data=r)
                ser.is_valid(raise_exception=True)
                ScreeningRule.objects.create(job_offer=instance, **ser.validated_data)
        self._apply_preselection_settings(instance, request)
        self._apply_selection_settings(instance, request)
        return instance

    def update(self, instance, validated_data):
        self._set_published_at_if_needed(validated_data, instance=instance)
        request = self.context.get('request')
        rules_data = self._parse_screening_rules(request)
        instance = super().update(instance, validated_data)
        if rules_data is not None:
            instance.screening_rules.all().delete()
            for r in rules_data:
                ser = ScreeningRuleWriteSerializer(data=r)
                ser.is_valid(raise_exception=True)
                ScreeningRule.objects.create(job_offer=instance, **ser.validated_data)
        self._apply_preselection_settings(instance, request)
        self._apply_selection_settings(instance, request)
        return instance


class JobOfferListSerializer(serializers.ModelSerializer):
    """Version allégée pour les listes."""
    class Meta:
        model = JobOffer
        fields = [
            'id', 'title', 'slug', 'company', 'status', 'contract_type',
            'location', 'country', 'published_at', 'created_at',
        ]


class JobOfferPublicSerializer(serializers.ModelSerializer):
    """Offre publique (sans infos sensibles). Document en URL absolue. company pour pré-remplir le formulaire par entreprise."""
    description_document_url = serializers.SerializerMethodField()

    class Meta:
        model = JobOffer
        fields = [
            'id', 'company', 'title', 'slug', 'description', 'description_document_url', 'requirements', 'benefits',
            'location', 'country', 'contract_type',
            'salary_min', 'salary_max', 'salary_currency', 'salary_visible',
            'published_at', 'deadline', 'created_at',
        ]

    def get_description_document_url(self, obj):
        if not obj.description_document:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.description_document.url)
        return obj.description_document.url


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    """Entrée leaderboard : application avec candidat, score, rang, statut, badge (Automatique/Manuel)."""
    rank = serializers.IntegerField(read_only=True)
    candidate = CandidateListSerializer(read_only=True)
    badge = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'rank', 'candidate', 'preselection_score', 'status', 'badge', 'created_at']

    def get_badge(self, obj):
        if obj.is_manually_adjusted or obj.manually_added_to_shortlist:
            return 'manual'
        return 'automatic'


class ShortlistEntrySerializer(serializers.ModelSerializer):
    """Entrée shortlist pour generate-shortlist."""
    candidate = CandidateListSerializer(read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'candidate', 'preselection_score', 'selection_score', 'status']
