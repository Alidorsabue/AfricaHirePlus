"""
Vues API candidats : liste/création, détail, export Excel, mon profil (candidat connecté).
Filtrage multi-tenant par company (recruteur = sa société uniquement).
"""
from io import BytesIO
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook

from .models import Candidate
from .serializers import CandidateSerializer, CandidateListSerializer, CandidateProfileSerializer
from apps.core.permissions import IsTenantOrSuperAdmin, IsCandidate


class MyCandidateProfileView(generics.GenericAPIView):
    """
    GET : retourne le profil candidat du compte connecté.
    - Si ?company=<id> : profil pour cette entreprise (pour pré-remplir le formulaire sur une offre de cette entreprise).
    - Sinon : dernier candidat mis à jour (comportement historique, ex. page « Mon profil »).
    PATCH : met à jour tous les profils candidat de l'utilisateur avec les données envoyées.
    """
    permission_classes = [IsCandidate]
    serializer_class = CandidateProfileSerializer

    def get_profile(self, company_id=None):
        qs = Candidate.objects.filter(user_id=self.request.user.id)
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs.order_by('-updated_at').first()

    def get(self, request):
        company_id = request.query_params.get('company')
        if company_id is not None:
            try:
                company_id = int(company_id)
            except (TypeError, ValueError):
                company_id = None
        profile = self.get_profile(company_id=company_id)
        if not profile:
            return Response(
                {'detail': 'Aucun profil candidat trouvé pour cette entreprise. Postulez à une offre pour en créer un.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profiles = list(
            Candidate.objects.filter(user_id=request.user.id)
        )
        if not profiles:
            return Response(
                {'detail': 'Aucun profil candidat à mettre à jour.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(profiles[0], data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        update_data = serializer.validated_data
        for candidate in profiles:
            for key, value in update_data.items():
                setattr(candidate, key, value)
            candidate.save(update_fields=list(update_data.keys()))
        # Retourner le profil (le premier ou le plus récent après save)
        updated = (
            Candidate.objects.filter(user_id=request.user.id)
            .order_by('-updated_at')
            .first()
        )
        return Response(self.get_serializer(updated).data)


class CandidateListCreateView(generics.ListCreateAPIView):
    """Liste des candidats du tenant + création. Filtres : country, experience_years."""
    serializer_class = CandidateSerializer
    permission_classes = [IsTenantOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['country', 'experience_years']

    def get_queryset(self):
        # Restreint aux candidats de l'entreprise du recruteur (ou tout pour super admin)
        qs = Candidate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_serializer_class(self):
        # Liste = version allégée ; détail/création = sérialiseur complet
        if self.request.method == 'GET' and not self.kwargs.get('pk'):
            return CandidateListSerializer
        return CandidateSerializer


class CandidateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Consultation, modification et suppression d'un candidat (scope tenant). GET = profil complet (CV, formations, expériences)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return CandidateProfileSerializer
        return CandidateSerializer

    def get_queryset(self):
        qs = Candidate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs


class ExportCandidatesExcelView(generics.GenericAPIView):
    """Export Excel des candidats du pool de l'entreprise (téléchargement fichier)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Candidate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get(self, request):
        qs = self.get_queryset()
        wb = Workbook()
        ws = wb.active
        ws.title = 'Candidats'
        ws.append(['ID', 'Nom', 'Prénom', 'Email', 'Téléphone', 'Pays', 'Années exp.', 'Poste actuel', 'Créé le'])
        for c in qs:
            ws.append([
                c.id, c.last_name, c.first_name, c.email, c.phone or '',
                c.country or '', c.experience_years or '', c.current_position or '',
                c.created_at.isoformat() if c.created_at else '',
            ])
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="candidats.xlsx"'
        return response
