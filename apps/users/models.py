"""
Modèle User personnalisé : rôles SuperAdmin (plateforme), Recruiter (par entreprise), Candidate (candidat).
Recruteur = company obligatoire ; Candidat = pas de company ; SuperAdmin = accès global.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.companies.models import Company


class User(AbstractUser):
    """Utilisateur : SuperAdmin, Recruiter (lié à une Company) ou Candidate."""

    class Role(models.TextChoices):
        SUPER_ADMIN = 'super_admin', 'Super Admin'
        RECRUITER = 'recruiter', 'Recruiter'
        CANDIDATE = 'candidate', 'Candidat'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RECRUITER,
        db_index=True,
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users',
        help_text='Obligatoire pour les Recruiters.',
    )
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', null=True, blank=True)

    class Meta:
        db_table = 'users_user'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['company', 'is_active']),
        ]
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return self.email or self.username

    @property
    def is_super_admin(self):
        return self.role == self.Role.SUPER_ADMIN

    @property
    def is_recruiter(self):
        return self.role == self.Role.RECRUITER

    @property
    def is_candidate(self):
        return self.role == self.Role.CANDIDATE

    def get_company_id(self):
        """Retourne l'ID entreprise du recruteur, ou None (super admin voit tout)."""
        return self.company_id if self.is_recruiter else None
