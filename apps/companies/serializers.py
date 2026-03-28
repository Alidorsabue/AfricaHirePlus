"""
Sérialiseurs entreprise et licence : champs complets en lecture/écriture.
"""
from rest_framework import serializers
from .models import Company, CompanyLicense


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

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        if instance.logo and request:
            ret['logo'] = request.build_absolute_uri(instance.logo.url)
        return ret


class CompanyLicenseSerializer(serializers.ModelSerializer):
    """Sérialiseur licence : lecture + renouvellement (superadmin)."""
    company_name = serializers.CharField(source='company.name', read_only=True)
    is_valid = serializers.BooleanField(read_only=True)
    duration_display = serializers.CharField(source='get_duration_months_display', read_only=True)

    class Meta:
        model = CompanyLicense
        fields = [
            'id', 'company', 'company_name', 'license_key', 'duration_months', 'duration_display',
            'start_date', 'end_date', 'is_valid', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'company', 'license_key', 'start_date', 'created_at', 'updated_at']


class CompanyLicenseRenewSerializer(serializers.Serializer):
    """Payload pour renouveler une licence : durée optionnelle (3, 6, 9, 12, 24 mois)."""
    duration_months = serializers.ChoiceField(
        choices=CompanyLicense.DURATION_CHOICES,
        required=False,
        help_text='Si absent, réutilise la durée actuelle de la licence.',
    )
