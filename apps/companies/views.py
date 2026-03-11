"""
Vues API entreprises : liste, création, détail, mise à jour, suppression (scope tenant).
Licences : liste, détail, renouvellement (superadmin uniquement).
"""
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Company, CompanyLicense
from .serializers import CompanySerializer, CompanyLicenseSerializer, CompanyLicenseRenewSerializer
from apps.core.permissions import IsTenantOrSuperAdmin, IsAdmin


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


# --- Licences (superadmin uniquement) ---

class CompanyLicenseListView(generics.ListAPIView):
    """Liste de toutes les licences (superadmin)."""
    serializer_class = CompanyLicenseSerializer
    permission_classes = [IsAdmin]
    queryset = CompanyLicense.objects.select_related('company').order_by('-end_date')


class CompanyLicenseDetailView(generics.RetrieveAPIView):
    """Détail d'une licence (superadmin)."""
    serializer_class = CompanyLicenseSerializer
    permission_classes = [IsAdmin]
    queryset = CompanyLicense.objects.select_related('company')


class CompanyLicenseRenewView(APIView):
    """Renouvellement d'une licence : POST avec option duration_months (3, 6, 9, 12, 24). Superadmin."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        license_obj = CompanyLicense.objects.filter(pk=pk).select_related('company').first()
        if not license_obj:
            return Response({'detail': 'Licence introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        ser = CompanyLicenseRenewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        duration = ser.validated_data.get('duration_months')
        license_obj.renew(duration_months=duration)
        return Response(CompanyLicenseSerializer(license_obj).data)
