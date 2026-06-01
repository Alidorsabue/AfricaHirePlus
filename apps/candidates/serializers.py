"""
Sérialiseurs candidats : lecture/écriture complète et version liste pour les APIs.
"""
from rest_framework import serializers
from .models import Candidate


class CandidateSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour détail et création/mise à jour d'un candidat (recruteur)."""
    class Meta:
        model = Candidate
        fields = [
            'id', 'company', 'email', 'first_name', 'last_name', 'phone',
            'resume', 'linkedin_url', 'portfolio_url', 'summary',
            'experience_years', 'education_level', 'current_position',
            'location', 'country', 'skills', 'tags',
            'is_anonymized', 'anonymized_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_anonymized', 'anonymized_at']

    def validate_tags(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Les tags doivent être une liste.")
        cleaned = []
        for t in value:
            if not isinstance(t, str):
                continue
            t = t.strip()[:64]
            if t:
                cleaned.append(t)
        # Dédoublonnage en gardant l'ordre
        seen = set()
        result = []
        for t in cleaned:
            tl = t.lower()
            if tl in seen:
                continue
            seen.add(tl)
            result.append(t)
        if len(result) > 30:
            raise serializers.ValidationError("Maximum 30 tags.")
        return result

    def validate_email(self, value):
        if value:
            return value.strip().lower()
        return value


class CandidateProfileSerializer(serializers.ModelSerializer):
    """Profil candidat complet pour GET/PATCH /candidates/me/ et détail recruteur (tous les champs)."""
    resume_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Candidate
        fields = [
            'id', 'company', 'email', 'first_name', 'last_name', 'phone',
            'title', 'preferred_name', 'date_of_birth', 'gender',
            'address', 'address_line2', 'city', 'postcode', 'country',
            'cell_number', 'nationality', 'second_nationality',
            'resume', 'resume_url', 'linkedin_url', 'portfolio_url', 'summary',
            'experience_years', 'education_level', 'current_position',
            'location', 'skills', 'raw_cv_text',
            'education', 'experience', 'languages', 'references',
            'tags',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'company', 'created_at', 'updated_at', 'raw_cv_text', 'tags',
        ]

    def get_resume_url(self, obj):
        if obj.resume:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.resume.url)
        return None

    def validate_email(self, value):
        if value:
            return value.strip().lower()
        return value

    def validate_experience_years(self, value):
        if value is None:
            return value
        if value < 0 or value > 70:
            raise serializers.ValidationError("Doit être compris entre 0 et 70 ans.")
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
            raise serializers.ValidationError("Vous devez avoir au moins 15 ans.")
        if age > 100:
            raise serializers.ValidationError("Âge invalide (> 100 ans).")
        return value

    def validate_linkedin_url(self, value):
        if value and 'linkedin.com' not in value.lower():
            raise serializers.ValidationError("L'URL LinkedIn doit pointer vers linkedin.com.")
        return value


class CandidateTagsSerializer(serializers.Serializer):
    """Pour PATCH /candidates/<id>/tags/."""

    tags = serializers.ListField(
        child=serializers.CharField(max_length=64, allow_blank=True, trim_whitespace=False),
        allow_empty=True,
    )

    def validate_tags(self, value):
        cleaned = []
        seen = set()
        for t in value:
            t = (t or '').strip()
            if not t:
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(t[:64])
        if len(cleaned) > 30:
            raise serializers.ValidationError("Maximum 30 tags.")
        return cleaned


class CandidateListSerializer(serializers.ModelSerializer):
    """Sérialiseur allégé pour les listes (ex. dans une candidature)."""
    class Meta:
        model = Candidate
        fields = [
            'id', 'email', 'first_name', 'last_name', 'company',
            'country', 'experience_years', 'current_position', 'created_at',
        ]


class CandidateListWithCvSerializer(serializers.ModelSerializer):
    """Liste candidat avec raw_cv_text pour l'onglet Analyse CV (requête ?with_cv=1)."""
    class Meta:
        model = Candidate
        fields = [
            'id', 'email', 'first_name', 'last_name', 'company',
            'country', 'experience_years', 'current_position', 'created_at',
            'raw_cv_text',
        ]
