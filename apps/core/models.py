"""
Mixins réutilisables : Soft Delete (deleted_at) et horodatage (created_at / updated_at).
Utilisés par Company, Candidate, JobOffer, Application, etc.
"""
from django.db import models
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    """Manager qui exclut par défaut les enregistrements avec deleted_at renseigné."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

    def with_deleted(self):
        """Retourne tous les enregistrements (y compris supprimés)."""
        return super().get_queryset()

    def deleted_only(self):
        """Retourne uniquement les enregistrements marqués supprimés."""
        return super().get_queryset().filter(deleted_at__isnull=False)


class SoftDeleteMixin(models.Model):
    """Soft delete : marquer deleted_at au lieu de supprimer en base (récupération possible)."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self, using=None, keep_parents=False):
        """Suppression réelle en base (irréversible)."""
        super().delete(using=using, keep_parents=keep_parents)

    @property
    def is_deleted(self):
        """True si l'enregistrement est marqué supprimé (soft delete)."""
        return self.deleted_at is not None


class TimeStampedMixin(models.Model):
    """Horodatage automatique : created_at à la création, updated_at à chaque sauvegarde."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
