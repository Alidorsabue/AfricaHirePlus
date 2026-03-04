"""
Sérialiseurs candidatures : lecture, écriture, mise à jour statut, soumission publique.
"""
import json
from rest_framework import serializers
from .models import Application
from apps.candidates.serializers import CandidateListSerializer, CandidateListWithCvSerializer
from apps.jobs.serializers import JobOfferListSerializer
from apps.jobs.models import JobOffer


class ListOrJSONStringField(serializers.Field):
    """Accepte une liste (payload JSON) ou une chaîne JSON (FormData) pour education/experience/langues/références."""
    def to_internal_value(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, str) and data.strip():
            try:
                parsed = json.loads(data)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        return []


class ApplicationSerializer(serializers.ModelSerializer):
    """Sérialiseur lecture avec candidat et offre en nested (pour listes et détail)."""
    candidate = CandidateListSerializer(read_only=True)
    job_offer = JobOfferListSerializer(read_only=True)
    cover_letter_document_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job_offer', 'candidate', 'status', 'cover_letter', 'cover_letter_document_url', 'source',
            'screening_score', 'preselection_score', 'selection_score',
            'preselection_score_details', 'selection_score_details',
            'is_manually_adjusted', 'manual_override_reason', 'manually_added_to_shortlist', 'email_sent',
            'notes', 'applied_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'applied_at', 'created_at', 'updated_at']

    def get_cover_letter_document_url(self, obj):
        if obj.cover_letter_document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_letter_document.url)
        return None


class ApplicationWithCvSerializer(serializers.ModelSerializer):
    """Liste onglet Analyse CV : candidat avec raw_cv_text, SANS ats_breakdown (chargé à la demande pour rapidité)."""
    candidate = CandidateListWithCvSerializer(read_only=True)
    job_offer = JobOfferListSerializer(read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job_offer', 'candidate', 'status', 'cover_letter', 'source',
            'screening_score', 'preselection_score', 'selection_score',
            'preselection_score_details', 'selection_score_details',
            'is_manually_adjusted', 'manual_override_reason', 'manually_added_to_shortlist', 'email_sent',
            'notes', 'applied_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'applied_at', 'created_at', 'updated_at']


class ApplicationWriteSerializer(serializers.ModelSerializer):
    """Pour création / mise à jour sans nested."""
    class Meta:
        model = Application
        fields = [
            'id', 'job_offer', 'candidate', 'status', 'cover_letter', 'source',
            'screening_score', 'preselection_score', 'selection_score',
            'preselection_score_details', 'selection_score_details',
            'is_manually_adjusted', 'manual_override_reason', 'manually_added_to_shortlist', 'email_sent',
            'notes', 'applied_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'applied_at', 'created_at', 'updated_at']


class ApplicationStatusUpdateSerializer(serializers.Serializer):
    """Mise à jour manuelle du statut (workflow)."""
    status = serializers.ChoiceField(choices=Application.Status.choices)


class PublicApplySerializer(serializers.Serializer):
    """Soumission candidature (utilisateur connecté requis)."""
    job_offer_id = serializers.IntegerField(required=False)
    job_offer_slug = serializers.SlugField(required=False)
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=100, required=False)
    last_name = serializers.CharField(max_length=100, required=False)
    cover_letter = serializers.CharField(required=False, allow_blank=True)
    cover_letter_document = serializers.FileField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    resume = serializers.FileField(required=False, allow_null=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    portfolio_url = serializers.URLField(required=False, allow_blank=True)
    summary = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    education_level = serializers.CharField(max_length=50, required=False, allow_blank=True)
    current_position = serializers.CharField(max_length=255, required=False, allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    title = serializers.CharField(max_length=20, required=False, allow_blank=True)
    preferred_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postcode = serializers.CharField(max_length=20, required=False, allow_blank=True)
    cell_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    nationality = serializers.CharField(max_length=100, required=False, allow_blank=True)
    second_nationality = serializers.CharField(max_length=100, required=False, allow_blank=True)
    skills = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    raw_cv_text = serializers.CharField(required=False, allow_blank=True)
    education = ListOrJSONStringField(required=False)
    experience = ListOrJSONStringField(required=False)
    languages = ListOrJSONStringField(required=False)
    references = ListOrJSONStringField(required=False)
    allow_contact_references = serializers.CharField(max_length=10, required=False, allow_blank=True)
    signature_text = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        # Offre obligatoire (id ou slug)
        if not data.get('job_offer_id') and not data.get('job_offer_slug'):
            raise serializers.ValidationError('Indiquez job_offer_id ou job_offer_slug.')
        # Si connecté, compléter email / prénom / nom depuis le compte
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if not data.get('email'):
                data['email'] = request.user.email
            if not data.get('first_name'):
                data['first_name'] = request.user.first_name or ''
            if not data.get('last_name'):
                data['last_name'] = request.user.last_name or ''
        if not data.get('email') or not data.get('first_name') or not data.get('last_name'):
            raise serializers.ValidationError(
                {'email': 'Email, prénom et nom sont requis (ou connectez-vous).'}
            )
        return data

    def get_job_offer(self):
        """Retourne l'offre publiée correspondant à l'id ou au slug fourni."""
        job_id = self.validated_data.get('job_offer_id')
        slug = self.validated_data.get('job_offer_slug')
        if job_id:
            return JobOffer.objects.filter(pk=job_id, status=JobOffer.Status.PUBLISHED).first()
        if slug:
            return JobOffer.objects.filter(slug=slug, status=JobOffer.Status.PUBLISHED).first()
        return None
