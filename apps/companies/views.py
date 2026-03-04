"""
Vues API entreprises : liste, création, détail, mise à jour, suppression (scope tenant).
"""
from rest_framework import generics
from .models import Company
from .serializers import CompanySerializer
from apps.core.permissions import IsTenantOrSuperAdmin


class CompanyListCreateView(generics.ListCreateAPIView):
    """Liste des entreprises (recruteur = sa société ; super admin = toutes) + création."""
    serializer_class = CompanySerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        # Recruteur : uniquement sa company ; super admin : toutes
        qs = Company.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(pk=company_id)
        return qs


class CompanyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, mise à jour et suppression (soft) d'une entreprise (scope tenant)."""
    serializer_class = CompanySerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Company.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(pk=company_id)
        return qs
