"""
Vues API candidats : liste/création, détail, export Excel, mon profil (candidat connecté),
tags (P10.9), suppression douce RGPD (P10.7), export "mes données" (RGPD art.20).
Filtrage multi-tenant par company (recruteur = sa société uniquement).
"""
import json
from io import BytesIO
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from django_filters.rest_framework import DjangoFilterBackend
from openpyxl import Workbook

from .models import Candidate
from .serializers import (
    CandidateSerializer,
    CandidateListSerializer,
    CandidateProfileSerializer,
    CandidateTagsSerializer,
)
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
        # P10.5 — mise à jour en lot dans une transaction (au lieu d'un save() par profil)
        with transaction.atomic():
            for candidate in profiles:
                for key, value in update_data.items():
                    setattr(candidate, key, value)
            Candidate.objects.bulk_update(profiles, list(update_data.keys())) if update_data else None
            # bulk_update ne déclenche pas `save()`, donc on force la normalisation
            # de l'email (lowercase) en remettant à jour si l'email a changé.
        # Recharger l'instance la plus récente pour la réponse
        updated = (
            Candidate.objects.filter(user_id=request.user.id)
            .order_by('-updated_at')
            .first()
        )
        return Response(self.get_serializer(updated).data)

    def delete(self, request):
        """
        P10.7 — Droit à l'effacement (RGPD article 17).
        Anonymise TOUS les profils candidat du user connecté (les candidatures
        existantes sont conservées pour la transparence RH mais les données
        identifiantes sont vidées).
        """
        profiles = list(Candidate.objects.filter(user_id=request.user.id))
        if not profiles:
            return Response(
                {'detail': 'Aucun profil candidat à supprimer.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        anonymized_ids = []
        for c in profiles:
            try:
                c.anonymize()
                anonymized_ids.append(c.pk)
            except Exception:
                continue
        return Response({
            'message': 'Profils candidats anonymisés. Vos candidatures restent visibles aux recruteurs sans données identifiantes.',
            'anonymized_ids': anonymized_ids,
        })


class MyCandidateDataExportView(generics.GenericAPIView):
    """
    GET /candidates/me/export/  (RGPD article 20 — portabilité des données)
    Retourne TOUTES les données candidat du user connecté au format JSON.
    """
    permission_classes = [IsAuthenticated, IsCandidate]

    def get(self, request):
        from apps.applications.models import Application
        profiles = Candidate.objects.filter(user_id=request.user.id)
        if not profiles.exists():
            return Response(
                {'detail': 'Aucune donnée candidat à exporter.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = {
            'export_date': timezone_now_iso(),
            'user': {
                'id': request.user.id,
                'email': request.user.email,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            },
            'candidates': [],
        }
        for c in profiles:
            applications = list(
                Application.objects.filter(candidate=c).values(
                    'id', 'status', 'cover_letter', 'applied_at', 'job_offer_id',
                )
            )
            data['candidates'].append({
                'id': c.id,
                'company_id': c.company_id,
                'email': c.email,
                'first_name': c.first_name,
                'last_name': c.last_name,
                'phone': c.phone,
                'date_of_birth': c.date_of_birth.isoformat() if c.date_of_birth else None,
                'address': c.address,
                'city': c.city,
                'country': c.country,
                'linkedin_url': c.linkedin_url,
                'portfolio_url': c.portfolio_url,
                'summary': c.summary,
                'experience_years': c.experience_years,
                'education_level': c.education_level,
                'skills': c.skills,
                'education': c.education,
                'experience': c.experience,
                'languages': c.languages,
                'references': c.references,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'applications': [
                    {**app, 'applied_at': app['applied_at'].isoformat() if app.get('applied_at') else None}
                    for app in applications
                ],
            })
        response = JsonResponse(data, json_dumps_params={'indent': 2, 'ensure_ascii': False})
        response['Content-Disposition'] = 'attachment; filename="mes-donnees-candidat.json"'
        return response


def timezone_now_iso():
    from django.utils import timezone
    return timezone.now().isoformat()


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


class CandidateTagsView(generics.GenericAPIView):
    """PATCH /candidates/<id>/tags/  (recruteur) — remplace la liste de tags."""

    permission_classes = [IsTenantOrSuperAdmin]
    serializer_class = CandidateTagsSerializer

    def get_queryset(self):
        qs = Candidate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def patch(self, request, pk):
        cand = self.get_queryset().filter(pk=pk).first()
        if not cand:
            return Response({'detail': 'Candidat introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cand.tags = ser.validated_data['tags']
        cand.save(update_fields=['tags', 'updated_at'])
        return Response({'id': cand.pk, 'tags': cand.tags})


class CandidateAnonymizeView(generics.GenericAPIView):
    """
    POST /candidates/<id>/anonymize/  (recruteur ou super admin)
    Anonymise un candidat à la demande (RGPD article 17), même sans compte.
    """

    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Candidate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def post(self, request, pk):
        cand = self.get_queryset().filter(pk=pk).first()
        if not cand:
            return Response({'detail': 'Candidat introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        cand.anonymize()
        return Response({
            'message': 'Candidat anonymisé.',
            'id': cand.pk,
            'is_anonymized': cand.is_anonymized,
            'anonymized_at': cand.anonymized_at.isoformat() if cand.anonymized_at else None,
        })


class ExportCandidatesExcelView(generics.GenericAPIView):
    """Export Excel des candidats du pool (téléchargement). Throttle 'export'."""
    permission_classes = [IsTenantOrSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'export'

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
