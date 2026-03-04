"""
Vues API candidatures : liste/création, détail, mes candidatures, postuler (public), mise à jour statut, screening, export Excel, prédiction score ML.
"""
import logging
from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import Application, MLScore
from .serializers import (
    ApplicationSerializer,
    ApplicationWriteSerializer,
    ApplicationWithCvSerializer,
    ApplicationStatusUpdateSerializer,
    PublicApplySerializer,
)
from .services import submit_application, apply_manual_override, job_accepts_applications
from apps.jobs.services import run_auto_preselection, refresh_preselection_scores_for_job
from apps.jobs.models import JobOffer, PreselectionSettings
from apps.emails.services import send_rejection_notification
from apps.core.permissions import IsTenantOrSuperAdmin, IsCandidate
from apps.candidates.serializers import CandidateProfileSerializer

logger = logging.getLogger(__name__)


class ApplicationListCreateView(generics.ListCreateAPIView):
    """Liste et création de candidatures (recruteur/super admin, filtré par statut/offre/candidat)."""
    permission_classes = [IsTenantOrSuperAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'job_offer', 'candidate']

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def get_serializer_class(self):
        # POST = écriture sans nested ; GET = lecture avec nested
        if self.request.method == 'POST':
            return ApplicationWriteSerializer
        if self.request.method == 'GET' and self.request.query_params.get('with_cv') == '1':
            return ApplicationWithCvSerializer
        return ApplicationSerializer

    def list(self, request, *args, **kwargs):
        # Mise à jour automatique des scores : si la liste est filtrée par offre et que l'offre
        # n'a pas de règles/critères et qu'il existe des candidatures sans score, on recalcule.
        job_id = request.query_params.get('job_offer')
        if job_id and request.method == 'GET':
            qs_tenant = self.get_queryset().filter(job_offer_id=job_id)
            if qs_tenant.filter(preselection_score__isnull=True).exists():
                first_app = qs_tenant.select_related('job_offer').first()
                job = first_app.job_offer if first_app else None
                if job and not job.screening_rules.exists():
                    settings = getattr(job, 'preselection_settings', None) or PreselectionSettings.objects.filter(job_offer=job).first()
                    criteria = getattr(settings, 'criteria_json', None) or {}
                    criteria_list = criteria.get('criteria') if isinstance(criteria, dict) else None
                    if not criteria_list:
                        try:
                            refresh_preselection_scores_for_job(job)
                        except Exception as e:
                            logger.warning("ApplicationListCreateView list: refresh_scores job_id=%s error=%s", job_id, e)
        return super().list(request, *args, **kwargs)


class MyApplicationsListView(generics.ListAPIView):
    """Liste des candidatures du candidat connecté (rôle candidat)."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated, IsCandidate]

    def get_queryset(self):
        return Application.objects.filter(
            candidate__user_id=self.request.user.id
        ).select_related('job_offer', 'candidate', 'job_offer__company').order_by('-applied_at')


class MyApplicationByJobView(generics.GenericAPIView):
    """
    GET : ma candidature pour une offre (job_offer_slug ou job_offer_id en query).
    Retourne les données complètes (candidat profil) pour pré-remplir le formulaire.
    404 si aucune candidature pour cette offre.
    """
    permission_classes = [IsAuthenticated, IsCandidate]

    def get(self, request):
        slug = request.query_params.get('job_offer_slug')
        job_id = request.query_params.get('job_offer_id')
        if not slug and not job_id:
            return Response(
                {'detail': 'Indiquez job_offer_slug ou job_offer_id.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Application.objects.filter(
            candidate__user_id=request.user.id
        ).select_related('job_offer', 'candidate', 'job_offer__company')
        if slug:
            qs = qs.filter(job_offer__slug=slug)
        else:
            try:
                qs = qs.filter(job_offer_id=int(job_id))
            except (TypeError, ValueError):
                return Response({'detail': 'job_offer_id invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        application = qs.first()
        if not application:
            return Response(
                {'detail': 'Aucune candidature trouvée pour cette offre.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        job = application.job_offer
        candidate_data = CandidateProfileSerializer(
            application.candidate,
            context={'request': request},
        ).data
        cover_letter_document_url = None
        if application.cover_letter_document:
            cover_letter_document_url = request.build_absolute_uri(application.cover_letter_document.url)
        return Response({
            'application': {
                'id': application.id,
                'status': application.status,
                'cover_letter': application.cover_letter,
                'applied_at': application.applied_at,
                'cover_letter_document_url': cover_letter_document_url,
            },
            'candidate': candidate_data,
            'job_still_open': job_accepts_applications(job),
        })


class ApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'une candidature (scope tenant)."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs


class ApplicationAtsBreakdownView(generics.RetrieveAPIView):
    """GET : détail du calcul ATS (mots-clés, niveau d'études, expérience, scores) pour une candidature. Chargé à la demande pour l'onglet Analyse CV."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def retrieve(self, request, *args, **kwargs):
        application = self.get_object()
        try:
            from ml.ats_score import get_ats_breakdown
            data = get_ats_breakdown(application)
            return Response(data)
        except Exception as e:
            logger.warning("ApplicationAtsBreakdownView error pk=%s: %s", application.pk, e)
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicApplyView(generics.GenericAPIView):
    """Postuler à une offre (connexion requise). Profil candidat lié au compte."""
    serializer_class = PublicApplySerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.get_job_offer()
        if not job:
            return Response(
                {'detail': 'Offre introuvable ou non publiée.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not job_accepts_applications(job):
            return Response(
                {'detail': 'Cette offre est clôturée. La date limite de candidature est dépassée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            # Soumission ou mise à jour via service : candidat créé/mis à jour, screening et email de confirmation
            application, is_update = submit_application(
                job_offer=job,
                email=serializer.validated_data['email'],
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name'],
                cover_letter=serializer.validated_data.get('cover_letter', ''),
                source='public',
                phone=serializer.validated_data.get('phone', ''),
                resume=serializer.validated_data.get('resume'),
                linkedin_url=serializer.validated_data.get('linkedin_url', ''),
                portfolio_url=serializer.validated_data.get('portfolio_url', ''),
                summary=serializer.validated_data.get('summary', ''),
                experience_years=serializer.validated_data.get('experience_years'),
                education_level=serializer.validated_data.get('education_level', ''),
                current_position=serializer.validated_data.get('current_position', ''),
                location=serializer.validated_data.get('location', ''),
                country=serializer.validated_data.get('country', ''),
                skills=serializer.validated_data.get('skills'),
                raw_cv_text=serializer.validated_data.get('raw_cv_text', ''),
                run_screening=True,
                send_confirmation_email=True,
                user=request.user,
                education=serializer.validated_data.get('education'),
                experience=serializer.validated_data.get('experience'),
                languages=serializer.validated_data.get('languages'),
                references=serializer.validated_data.get('references'),
                cover_letter_document=serializer.validated_data.get('cover_letter_document'),
                signature_text=serializer.validated_data.get('signature_text', ''),
                title=serializer.validated_data.get('title', ''),
                preferred_name=serializer.validated_data.get('preferred_name', ''),
                date_of_birth=serializer.validated_data.get('date_of_birth'),
                gender=serializer.validated_data.get('gender', ''),
                address=serializer.validated_data.get('address', ''),
                address_line2=serializer.validated_data.get('address_line2', ''),
                city=serializer.validated_data.get('city', ''),
                postcode=serializer.validated_data.get('postcode', ''),
                cell_number=serializer.validated_data.get('cell_number', ''),
                nationality=serializer.validated_data.get('nationality', ''),
                second_nationality=serializer.validated_data.get('second_nationality', ''),
            )
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            raise
        # Ne pas envoyer d'email de confirmation en cas de mise à jour (déjà géré dans submit_application)
        if is_update:
            return Response(
                {
                    'message': 'Candidature mise à jour.',
                    'application_id': application.id,
                    'status': application.status,
                    'screening_score': getattr(application, 'preselection_score', None) or application.screening_score,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                'message': 'Candidature enregistrée.',
                'application_id': application.id,
                'status': application.status,
                'screening_score': application.screening_score,
            },
            status=status.HTTP_201_CREATED,
        )


class ApplicationStatusUpdateView(generics.GenericAPIView):
    """Mise à jour manuelle du statut (applied → preselected → shortlisted → rejected)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def patch(self, request, pk):
        app = self.get_queryset().filter(pk=pk).first()
        if not app:
            return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        ser = ApplicationStatusUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data['status']
        app.status = new_status
        app.save(update_fields=['status', 'updated_at'])
        # Envoi email de refus si statut passé à rejected
        if new_status == Application.Status.REJECTED:
            try:
                send_rejection_notification(
                    company=app.job_offer.company,
                    candidate_name=app.candidate.get_full_name(),
                    candidate_email=app.candidate.email,
                    job_title=app.job_offer.title,
                )
            except Exception:
                pass
        return Response(ApplicationSerializer(app).data)


class ApplicationManualOverrideView(generics.GenericAPIView):
    """POST /applications/{id}/manual-override/ — ADD_TO_SHORTLIST, REMOVE_FROM_SHORTLIST, FORCE_STATUS, UPDATE_SCORE."""
    permission_classes = [IsTenantOrSuperAdmin]
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def post(self, request, pk):
        app = self.get_queryset().filter(pk=pk).first()
        if not app:
            return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        action = request.data.get('action')
        if not action:
            return Response({'action': 'Requis.'}, status=status.HTTP_400_BAD_REQUEST)
        allowed = {'ADD_TO_SHORTLIST', 'REMOVE_FROM_SHORTLIST', 'FORCE_STATUS', 'UPDATE_SCORE'}
        if action not in allowed:
            return Response(
                {'action': f'Doit être l\'un de: {", ".join(sorted(allowed))}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reason = request.data.get('reason', '')
        new_status = request.data.get('new_status')
        new_score = request.data.get('new_score')
        if new_score is not None:
            try:
                new_score = float(new_score)
            except (TypeError, ValueError):
                return Response({'new_score': 'Doit être un nombre.'}, status=status.HTTP_400_BAD_REQUEST)
        apply_manual_override(app, action, reason=reason, new_status=new_status, new_score=new_score)
        app.refresh_from_db()
        return Response(ApplicationSerializer(app).data)


class ApplicationRunScreeningView(generics.GenericAPIView):
    """Relance la présélection automatique sur une candidature."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def post(self, request, pk):
        app = self.get_queryset().filter(pk=pk).first()
        if not app:
            return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        updated = run_auto_preselection(app)
        app.refresh_from_db()
        return Response({
            'screening_score': app.screening_score,
            'status': app.status,
            'preselected': updated,
        })


class ApplicationPredictScoreView(generics.GenericAPIView):
    """
    POST /applications/{id}/predict-score/
    Extrait les features, applique le modèle ML, enregistre MLScore et retourne le score.
    Traçabilité : model_version, date de prédiction, logs et audit trail.
    """
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def post(self, request, pk):
        app = self.get_queryset().filter(pk=pk).first()
        if not app:
            return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            from ml.inference import predict_score
            from ml.feature_engineering import extract_features
            from ml.model_registry import get_current_model_version
        except ImportError as e:
            logger.exception("predict-score: import ml failed application_id=%s", pk)
            return Response(
                {'detail': 'Module ML indisponible.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            features = extract_features(app)
            predicted_score, confidence_score, ml_explanation_json = predict_score(app)
            model_version = get_current_model_version()
            ml_score = MLScore.objects.create(
                application=app,
                model_version=model_version,
                predicted_score=predicted_score,
                confidence_score=confidence_score,
                features_json=features,
                ml_explanation_json=ml_explanation_json,
            )
            logger.info(
                "predict-score: application_id=%s model_version=%s predicted_score=%.2f ml_score_id=%s user_id=%s (audit)",
                app.id,
                model_version,
                predicted_score,
                ml_score.id,
                getattr(request.user, 'id', None),
            )
        except Exception as e:
            logger.exception("predict-score: error application_id=%s", pk)
            return Response(
                {'detail': 'Erreur lors de la prédiction.', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                'application_id': app.id,
                'predicted_score': predicted_score,
                'confidence_score': confidence_score,
                'model_version': model_version,
                'features': features,
                'ml_score_id': ml_score.id,
                'created_at': ml_score.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


def _applications_to_rows(queryset):
    """Génère les lignes pour export Excel (en-tête + une ligne par candidature)."""
    yield ['ID', 'Candidat', 'Email', 'Offre', 'Statut', 'Score', 'Date candidature']
    for app in queryset:
        yield [
            app.id,
            app.candidate.get_full_name(),
            app.candidate.email,
            app.job_offer.title,
            app.status,
            app.screening_score or '',
            app.applied_at.isoformat() if app.applied_at else '',
        ]


def _build_applications_xlsx(queryset):
    """Construit un classeur Excel des candidatures et retourne les bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Candidatures'
    for row in _applications_to_rows(queryset):
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


class ExportApplicationsExcelView(generics.GenericAPIView):
    """Export Excel des candidatures (filtré par statut optionnel)."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def get(self, request):
        status_filter = request.query_params.get('status')
        qs = self.get_queryset()
        if status_filter:
            qs = qs.filter(status=status_filter)
        content = _build_applications_xlsx(qs)
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="candidatures.xlsx"'
        return response


class ExportShortlistedExcelView(generics.GenericAPIView):
    """Export Excel des présélectionnés / shortlistés."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = Application.objects.filter(
            status__in=[Application.Status.PRESELECTED, Application.Status.SHORTLISTED]
        ).select_related('job_offer', 'candidate', 'job_offer__company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def get(self, request):
        qs = self.get_queryset()
        content = _build_applications_xlsx(qs)
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="preselectionnes.xlsx"'
        return response
