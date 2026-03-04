"""
Vues API offres d'emploi : liste/création, détail, clôture, export Excel (tenant) ; liste et détail publics (sans auth).
"""
import logging
from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import JobOffer
from .serializers import (
    JobOfferSerializer,
    JobOfferListSerializer,
    JobOfferPublicSerializer,
    LeaderboardEntrySerializer,
)
from .services import (
    close_offer,
    compute_selection,
    compute_kpi,
    generate_shortlist_xlsx,
    refresh_preselection_scores_for_job,
    simulate_selection,
)
from apps.applications.models import Application
from apps.core.permissions import IsTenantOrSuperAdmin

logger = logging.getLogger(__name__)


class JobOfferListCreateView(generics.ListCreateAPIView):
    """Liste des offres du tenant + création. Filtres : status, contract_type, country."""
    serializer_class = JobOfferSerializer
    permission_classes = [IsTenantOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'contract_type', 'country']

    def get_queryset(self):
        qs = JobOffer.objects.select_related('company').prefetch_related('screening_rules')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == 'GET' and not self.kwargs.get('pk'):
            return JobOfferListSerializer
        return JobOfferSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('JobOffer create validation errors: %s', serializer.errors)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        # Rattacher l'offre à l'entreprise du recruteur (ou celle fournie pour super admin)
        company_id = self.request.user.get_company_id()
        if company_id is None:
            company = serializer.validated_data.get('company')
            company_id = company.pk if company else None
        if company_id is None:
            raise ValidationError({'company': 'Ce champ est requis.'})
        serializer.save(created_by=self.request.user, company_id=company_id)


class JobOfferDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'une offre (scope tenant)."""
    serializer_class = JobOfferSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = JobOffer.objects.select_related('company').prefetch_related(
            'screening_rules', 'preselection_settings', 'selection_settings'
        )
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs


class JobOfferCloseView(generics.GenericAPIView):
    """POST /jobs/{id}/close/ — Clôture l'offre (status=CLOSED, closed_at rempli). Bloque les nouvelles candidatures."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = JobOffer.objects.filter(status__in=[JobOffer.Status.DRAFT, JobOffer.Status.PUBLISHED])
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def post(self, request, pk):
        job = self.get_queryset().filter(pk=pk).first()
        if not job:
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        close_offer(job)
        job.refresh_from_db()
        return Response({
            'message': 'Offre clôturée.',
            'job': JobOfferListSerializer(job).data,
        })


class JobOfferRefreshScoresView(generics.GenericAPIView):
    """POST /jobs/{id}/refresh-scores/ — Recalcule les scores de présélection pour toutes les candidatures de l'offre (ATS JD vs CV si pas de règles)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = JobOffer.objects.select_related('company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def post(self, request, pk):
        job = self.get_queryset().filter(pk=pk).first()
        if not job:
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        updated = refresh_preselection_scores_for_job(job)
        return Response({
            'message': f'Scores recalculés pour {updated} candidature(s).',
            'updated_count': updated,
        })


def _job_queryset_tenant(request):
    qs = JobOffer.objects.select_related('company')
    company_id = request.user.get_company_id()
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    return qs


class JobOfferLeaderboardView(generics.GenericAPIView):
    """GET /jobs/{id}/leaderboard/ — Candidats présélectionnés ET shortlistés, triés par preselection_score DESC avec rang (Window). Les shortlistés restent dans le classement mais ne figurent plus dans l’ajustement manuel."""
    permission_classes = [IsTenantOrSuperAdmin]
    serializer_class = LeaderboardEntrySerializer

    def get_queryset(self):
        return Application.objects.filter(
            job_offer_id=self.kwargs['pk'],
            status__in=[Application.Status.PRESELECTED, Application.Status.SHORTLISTED],
        ).select_related('candidate', 'job_offer')

    def get(self, request, pk):
        if not _job_queryset_tenant(request).filter(pk=pk).exists():
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        from django.db.models import F, Window
        from django.db.models.functions import RowNumber
        qs = (
            self.get_queryset()
            .annotate(
                rank=Window(
                    expression=RowNumber(),
                    order_by=[F('preselection_score').desc(nulls_last=True), 'id'],
                )
            )
            .order_by('rank')
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


class JobOfferSimulateShortlistView(generics.GenericAPIView):
    """POST /jobs/{id}/simulate-shortlist/ — Simule la shortlist (threshold, max_candidates). Aucun changement en base."""
    permission_classes = [IsTenantOrSuperAdmin]

    def post(self, request, pk):
        job = _job_queryset_tenant(request).filter(pk=pk).first()
        if not job:
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        threshold = request.data.get('threshold')
        max_candidates = request.data.get('max_candidates')
        if threshold is None:
            return Response(
                {'threshold': 'Requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return Response(
                {'threshold': 'Doit être un nombre.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        max_candidates = int(max_candidates) if max_candidates is not None else 0
        result = simulate_selection(job, threshold=threshold, max_candidates=max_candidates)
        return Response({'shortlist': result})


class JobOfferGenerateShortlistView(generics.GenericAPIView):
    """POST /jobs/{id}/generate-shortlist/ — Génère la shortlist (AUTO ou SEMI_AUTOMATIC via bouton)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def post(self, request, pk):
        job = _job_queryset_tenant(request).filter(pk=pk).select_related('company').first()
        if not job:
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        shortlisted = compute_selection(job)
        from .serializers import ShortlistEntrySerializer
        return Response({
            'message': 'Shortlist générée.',
            'shortlist': ShortlistEntrySerializer(shortlisted, many=True).data,
        })


class JobOfferKpiView(generics.GenericAPIView):
    """GET /jobs/{id}/kpi/ — Dashboard KPI (total_applications, taux de rejet, scores moyens, etc.)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get(self, request, pk):
        if not _job_queryset_tenant(request).filter(pk=pk).exists():
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        job = JobOffer.objects.get(pk=pk)
        kpi = compute_kpi(job)
        return Response(kpi)


class JobOfferExportShortlistView(generics.GenericAPIView):
    """GET /jobs/{id}/export-shortlist/ — Export Excel de la shortlist."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get(self, request, pk):
        job = _job_queryset_tenant(request).filter(pk=pk).select_related('created_by').first()
        if not job:
            return Response({'detail': 'Offre introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        recruiter_name = ''
        if job.created_by:
            recruiter_name = getattr(job.created_by, 'get_full_name', lambda: str(job.created_by))()
        xlsx_bytes = generate_shortlist_xlsx(job, recruiter_name=recruiter_name)
        response = HttpResponse(
            xlsx_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="shortlist_%s.xlsx"' % pk
        return response


class ExportJobOffersExcelView(generics.GenericAPIView):
    """Export Excel des offres d'emploi du tenant."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = JobOffer.objects.select_related('company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get(self, request):
        qs = self.get_queryset()
        wb = Workbook()
        ws = wb.active
        ws.title = 'Offres'
        ws.append(['ID', 'Titre', 'Statut', 'Localisation', 'Type de contrat', 'Créé le'])
        for j in qs:
            ws.append([
                j.id,
                j.title or '',
                j.status or '',
                j.location or '',
                j.contract_type or '',
                j.created_at.isoformat() if j.created_at else '',
            ])
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="offres.xlsx"'
        return response


# ——— Offres publiques (sans authentification) ———

class PublicJobOffersListView(generics.ListAPIView):
    """Liste des offres publiées (accès public, filtres contract_type / country)."""
    serializer_class = JobOfferPublicSerializer
    permission_classes = [AllowAny]
    queryset = JobOffer.objects.filter(status=JobOffer.Status.PUBLISHED).select_related('company')
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['contract_type', 'country']


class PublicJobOfferDetailView(generics.RetrieveAPIView):
    """Détail d'une offre publiée (accès public)."""
    serializer_class = JobOfferPublicSerializer
    permission_classes = [AllowAny]
    queryset = JobOffer.objects.filter(status=JobOffer.Status.PUBLISHED)
    lookup_field = 'slug'
    lookup_url_kwarg = 'slug'
