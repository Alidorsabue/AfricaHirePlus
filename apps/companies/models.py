"""
Modèle Company : entreprise cliente (multi-tenant).
Chaque recruteur est rattaché à une company ; offres et candidats sont scopés par company.
"""
from django.db import models

from apps.core.models import SoftDeleteMixin, TimeStampedMixin


class Company(SoftDeleteMixin, TimeStampedMixin, models.Model):
    """Entreprise cliente de l'ATS : nom, slug unique, logo, contact, paramètres."""

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)  # Unique plateforme
    logo = models.ImageField(upload_to='companies/logos/%Y/%m/', null=True, blank=True)
    website = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)

    # Contact / siège
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)

    # Paramètres
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = 'companies_company'
        verbose_name = 'Entreprise'
        verbose_name_plural = 'Entreprises'
        indexes = [
            models.Index(fields=['is_active', 'deleted_at']),
        ]

    def __str__(self):
        return self.name
