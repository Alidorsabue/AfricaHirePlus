"""
Sérialiseur entreprise : champs complets (nom, slug, logo, contact, etc.) en lecture/écriture.
"""
from rest_framework import serializers
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Sérialiseur complet Company (slug en lecture seule)."""
    class Meta:
        model = Company
        fields = [
            'id', 'name', 'slug', 'logo', 'website', 'description',
            'email', 'phone', 'address', 'city', 'country',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
