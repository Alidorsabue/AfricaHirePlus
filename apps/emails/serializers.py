"""
Sérialiseur template d'email : champs complets, validation unicité (company, template_type).
"""
from rest_framework import serializers
from .models import EmailTemplate
from apps.companies.models import Company


class EmailTemplateSerializer(serializers.ModelSerializer):
    """Lecture/écriture template : sujet, body_html, body_text, type, company (optionnel pour recruteur)."""
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        required=False,
        allow_null=True,
        default=None,
    )
    body_html = serializers.CharField(required=False, allow_blank=True, default='')
    body_text = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = EmailTemplate
        fields = [
            'id', 'company', 'name', 'template_type', 'subject',
            'body_html', 'body_text', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Recruteur ne envoie pas company : rempli côté vue (perform_create)
        if self.fields.get('company'):
            self.fields['company'].required = False

    def validate(self, data):
        # Vérifier unicité (company, template_type) avant création
        company = data.get('company')
        template_type = data.get('template_type')
        if not template_type:
            return data
        # company peut être résolu dans perform_create (recruteur)
        if not company and self.context.get('request'):
            company = getattr(self.context['request'].user, 'company', None)
        if company and self.instance is None:
            if EmailTemplate.objects.filter(company=company, template_type=template_type).exists():
                raise serializers.ValidationError({
                    'template_type': 'Un template avec ce type existe déjà pour cette entreprise.',
                })
        return data
