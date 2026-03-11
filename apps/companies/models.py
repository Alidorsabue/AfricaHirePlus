"""
Modèle Company : entreprise cliente (multi-tenant).
Chaque recruteur est rattaché à une company ; offres et candidats sont scopés par company.
Licence : une licence unique par entreprise, renouvelable (3, 6, 9 mois, 1 an, 2 ans).
"""
import secrets
import string
from datetime import timedelta
from django.db import models
from django.utils import timezone

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


def generate_license_key():
    """Génère une clé de licence unique (ex: AHP-XXXX-XXXX-XXXX)."""
    from apps.companies.models import CompanyLicense
    alphabet = string.ascii_uppercase + string.digits
    part = lambda n: ''.join(secrets.choice(alphabet) for _ in range(n))
    key = f"AHP-{part(4)}-{part(4)}-{part(4)}"
    while CompanyLicense.objects.filter(license_key=key).exists():
        key = f"AHP-{part(4)}-{part(4)}-{part(4)}"
    return key


class CompanyLicense(TimeStampedMixin, models.Model):
    """
    Licence unique par entreprise, renouvelable.
    Durées possibles : 3, 6, 9 mois, 1 an, 2 ans.
    """
    DURATION_3_MONTHS = 3
    DURATION_6_MONTHS = 6
    DURATION_9_MONTHS = 9
    DURATION_1_YEAR = 12
    DURATION_2_YEARS = 24
    DURATION_CHOICES = [
        (DURATION_3_MONTHS, '3 mois'),
        (DURATION_6_MONTHS, '6 mois'),
        (DURATION_9_MONTHS, '9 mois'),
        (DURATION_1_YEAR, '1 an'),
        (DURATION_2_YEARS, '2 ans'),
    ]

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name='license',
        primary_key=False,
    )
    license_key = models.CharField(max_length=32, unique=True, db_index=True)
    duration_months = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=DURATION_1_YEAR)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    class Meta:
        db_table = 'companies_companylicense'
        verbose_name = 'Licence entreprise'
        verbose_name_plural = 'Licences entreprises'

    def __str__(self):
        return f"{self.license_key} — {self.company.name} (jusqu'au {self.end_date})"

    @property
    def is_valid(self):
        """True si la licence est encore valide (end_date >= aujourd'hui)."""
        return self.end_date >= timezone.now().date()

    def renew(self, duration_months=None):
        """
        Prolonge la licence à partir de la fin actuelle (ou d'aujourd'hui si expirée).
        duration_months : 3, 6, 9, 12 ou 24 ; si None, réutilise duration_months actuel.
        """
        today = timezone.now().date()
        base = self.end_date if self.end_date >= today else today
        months = duration_months if duration_months is not None else self.duration_months
        # ~30 jours par mois pour éviter la dépendance dateutil
        self.end_date = base + timedelta(days=months * 30)
        self.save(update_fields=['end_date', 'updated_at'])
