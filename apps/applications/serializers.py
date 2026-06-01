"""
Sérialiseurs candidatures : lecture, écriture, mise à jour statut, soumission publique.

P10 — Séparation stricte des sérialiseurs :
- `ApplicationSerializer`            : lecture recruteur (tous les détails internes)
- `ApplicationWriteSerializer`       : POST/PUT recruteur — champs internes en read_only
- `ApplicationCandidateSerializer`   : lecture candidat (sans notes, scores internes, etc.) — RGPD
- `ApplicationStatusUpdateSerializer`: PATCH statut uniquement
- `PublicApplySerializer`            : soumission candidat (validation stricte)
"""
import json
import os

from django.conf import settings
from rest_framework import serializers
from .models import Application, ApplicationNote, ApplicationAuditLog
from apps.candidates.serializers import CandidateListSerializer, CandidateListWithCvSerializer
from apps.jobs.serializers import JobOfferListSerializer
from apps.jobs.models import JobOffer

# ---------------------------------------------------------------------------
# Validation des fichiers (P10.2)
# ---------------------------------------------------------------------------
# Tailles maximales (Mo) — surchargeables par settings.
DEFAULT_CV_MAX_SIZE_MB = 10
DEFAULT_COVER_LETTER_MAX_SIZE_MB = 5

# Extensions et MIME acceptés pour les CV.
CV_ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt'}
CV_ALLOWED_MIME = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.oasis.opendocument.text',
    'application/rtf',
    'text/rtf',
    'text/plain',
}

# Extensions / MIME pour la lettre de motivation (PDF + Word + images).
COVER_LETTER_ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.odt', '.rtf', '.txt'}
COVER_LETTER_ALLOWED_MIME = CV_ALLOWED_MIME

# Extensions notoirement dangereuses (refusées peu importe le MIME annoncé).
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.scr', '.msi', '.vbs', '.js', '.jar',
    '.sh', '.ps1', '.psm1', '.dll', '.so', '.pif', '.htm', '.html', '.svg',
    '.php', '.phtml', '.asp', '.aspx', '.jsp',
}


def _resolve_max_size(setting_name: str, default_mb: int) -> int:
    """Retourne la taille max en octets configurée (ou défaut)."""
    mb = getattr(settings, setting_name, default_mb)
    try:
        mb = int(mb)
    except (TypeError, ValueError):
        mb = default_mb
    return max(1, mb) * 1024 * 1024


def _validate_uploaded_file(
    uploaded,
    *,
    field_label: str,
    max_bytes: int,
    allowed_extensions: set[str],
    allowed_mime: set[str],
):
    """Valide taille, extension, MIME et bloque les extensions dangereuses."""
    if uploaded is None:
        return
    size = getattr(uploaded, 'size', None)
    if size is not None and size > max_bytes:
        raise serializers.ValidationError(
            f"{field_label} : fichier trop volumineux ({size / 1024 / 1024:.1f} Mo). "
            f"Limite : {max_bytes / 1024 / 1024:.0f} Mo."
        )
    name = (getattr(uploaded, 'name', '') or '').strip().lower()
    if not name:
        raise serializers.ValidationError(f"{field_label} : nom de fichier manquant.")
    ext = os.path.splitext(name)[1].lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise serializers.ValidationError(
            f"{field_label} : type de fichier non autorisé ({ext})."
        )
    if ext and ext not in allowed_extensions:
        raise serializers.ValidationError(
            f"{field_label} : extension non supportée ({ext}). "
            f"Acceptées : {', '.join(sorted(allowed_extensions))}."
        )
    ct = (getattr(uploaded, 'content_type', '') or '').lower()
    # Si un content_type est annoncé, vérifier qu'il est autorisé (on tolère l'absence
    # qui peut arriver avec certaines libs/clients HTTP).
    if ct and ct not in allowed_mime and not ct.startswith('application/octet-stream'):
        raise serializers.ValidationError(
            f"{field_label} : type MIME non supporté ({ct})."
        )


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
    """
    Création / mise à jour (recruteur). P10 : scores, flags d'override et statut
    de présélection ne sont PAS modifiables via cette interface — il faut passer
    par les endpoints dédiés (`status/`, `manual-override/`, `run-screening/`)
    qui consignent un audit log.
    """

    class Meta:
        model = Application
        fields = [
            'id', 'job_offer', 'candidate', 'status', 'cover_letter', 'source',
            'screening_score', 'preselection_score', 'selection_score',
            'preselection_score_details', 'selection_score_details',
            'is_manually_adjusted', 'manual_override_reason', 'manually_added_to_shortlist', 'email_sent',
            'notes', 'applied_at', 'created_at', 'updated_at',
        ]
        # Tous les champs scoring / workflow / audit sont read-only ici.
        read_only_fields = [
            'id', 'applied_at', 'created_at', 'updated_at',
            'screening_score', 'preselection_score', 'selection_score',
            'preselection_score_details', 'selection_score_details',
            'is_manually_adjusted', 'manual_override_reason', 'manually_added_to_shortlist',
            'email_sent',
        ]


class ApplicationCandidateSerializer(serializers.ModelSerializer):
    """
    Vue candidat (RGPD) : retire les champs internes (notes, scores détaillés,
    raisons d'override, flags manuels) qui ne le concernent pas.
    """

    job_offer = JobOfferListSerializer(read_only=True)
    cover_letter_document_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'job_offer', 'status', 'cover_letter', 'cover_letter_document_url',
            'applied_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_cover_letter_document_url(self, obj):
        if obj.cover_letter_document:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_letter_document.url)
        return None


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

    # ------------------------------------------------------------------ P10.2
    # Validation des fichiers (taille / MIME / extension)
    # ------------------------------------------------------------------
    def validate_resume(self, value):
        _validate_uploaded_file(
            value,
            field_label='CV',
            max_bytes=_resolve_max_size('CV_MAX_SIZE_MB', DEFAULT_CV_MAX_SIZE_MB),
            allowed_extensions=CV_ALLOWED_EXTENSIONS,
            allowed_mime=CV_ALLOWED_MIME,
        )
        return value

    def validate_cover_letter_document(self, value):
        _validate_uploaded_file(
            value,
            field_label='Lettre de motivation',
            max_bytes=_resolve_max_size('COVER_LETTER_MAX_SIZE_MB', DEFAULT_COVER_LETTER_MAX_SIZE_MB),
            allowed_extensions=COVER_LETTER_ALLOWED_EXTENSIONS,
            allowed_mime=COVER_LETTER_ALLOWED_MIME,
        )
        return value

    def validate_experience_years(self, value):
        if value is None:
            return value
        if value < 0 or value > 70:
            raise serializers.ValidationError(
                "Doit être compris entre 0 et 70 ans."
            )
        return value

    def validate_date_of_birth(self, value):
        if value is None:
            return value
        from datetime import date

        today = date.today()
        if value.year < 1900:
            raise serializers.ValidationError("Date de naissance invalide (avant 1900).")
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 15:
            raise serializers.ValidationError(
                "Vous devez avoir au moins 15 ans pour postuler."
            )
        if age > 100:
            raise serializers.ValidationError("Âge invalide (> 100 ans).")
        return value

    def validate_linkedin_url(self, value):
        if not value:
            return value
        if 'linkedin.com' not in value.lower():
            raise serializers.ValidationError(
                "L'URL LinkedIn doit pointer vers linkedin.com."
            )
        return value

    def validate_cover_letter(self, value):
        # Garde-fou contre les payloads gigantesques injectés en texte.
        if value and len(value) > 20_000:
            raise serializers.ValidationError(
                "La lettre de motivation ne peut pas dépasser 20 000 caractères."
            )
        return value

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

            # P10.1 : empêcher l'usurpation d'identité — un user candidat ne peut
            # poster qu'avec son propre email (sauf super_admin / recruteur qui
            # peut postuler pour un tiers en interne).
            role = getattr(request.user, 'role', None)
            if role == 'candidate':
                provided_email = (data.get('email') or '').strip().lower()
                account_email = (request.user.email or '').strip().lower()
                if provided_email and account_email and provided_email != account_email:
                    raise serializers.ValidationError({
                        'email': "Vous ne pouvez postuler qu'avec votre adresse de compte."
                    })

        if not data.get('email') or not data.get('first_name') or not data.get('last_name'):
            raise serializers.ValidationError(
                {'email': 'Email, prénom et nom sont requis (ou connectez-vous).'}
            )

        # Validation de la signature électronique (si fournie)
        signature = (data.get('signature_text') or '').strip()
        if signature:
            first = (data.get('first_name') or '').strip().lower()
            last = (data.get('last_name') or '').strip().lower()
            email = (data.get('email') or '').strip().lower()
            sig_lower = signature.lower()
            if (
                not (first and first in sig_lower)
                and not (last and last in sig_lower)
                and not (email and email in sig_lower)
            ):
                raise serializers.ValidationError({
                    'signature_text': (
                        "La signature doit contenir votre prénom, votre nom ou votre email."
                    )
                })
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


# ---------------------------------------------------------------------------
# Notes internes et journal d'audit (P10.3 / P10.9)
# ---------------------------------------------------------------------------
class ApplicationNoteSerializer(serializers.ModelSerializer):
    """Note interne d'une candidature (recruteur). Auteur et application en lecture seule
    (l'application est imposée par l'URL nested)."""

    author_name = serializers.SerializerMethodField(read_only=True)
    author_email = serializers.CharField(source='author.email', read_only=True)

    class Meta:
        model = ApplicationNote
        fields = [
            'id', 'application', 'author', 'author_name', 'author_email',
            'body', 'is_pinned', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'application', 'author', 'author_name', 'author_email',
            'created_at', 'updated_at',
        ]

    def get_author_name(self, obj):
        if not obj.author:
            return ''
        return (
            f'{obj.author.first_name} {obj.author.last_name}'.strip()
            or obj.author.username
            or obj.author.email
        )

    def validate_body(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Le contenu de la note ne peut pas être vide.")
        if len(value) > 5_000:
            raise serializers.ValidationError("Maximum 5 000 caractères par note.")
        return value


class ApplicationAuditLogSerializer(serializers.ModelSerializer):
    """Lecture seule du journal d'audit (recruteur)."""

    actor_name = serializers.SerializerMethodField(read_only=True)
    action_label = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = ApplicationAuditLog
        fields = [
            'id', 'application', 'actor', 'actor_name', 'action', 'action_label',
            'payload_before', 'payload_after', 'reason',
            'ip_address', 'user_agent', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor:
            return 'Système'
        return (
            f'{obj.actor.first_name} {obj.actor.last_name}'.strip()
            or obj.actor.username
            or obj.actor.email
        )
