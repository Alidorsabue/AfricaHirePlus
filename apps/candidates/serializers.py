"""
Sérialiseurs candidats : lecture/écriture complète et version liste pour les APIs.
"""
from rest_framework import serializers
from .models import Candidate


class CandidateSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour détail et création/mise à jour d'un candidat."""
    class Meta:
        model = Candidate
        fields = [
            'id', 'company', 'email', 'first_name', 'last_name', 'phone',
            'resume', 'linkedin_url', 'portfolio_url', 'summary',
            'experience_years', 'education_level', 'current_position',
            'location', 'country', 'skills', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'company', 'created_at', 'updated_at', 'raw_cv_text']

    def get_resume_url(self, obj):
        if obj.resume:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.resume.url)
        return None


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
