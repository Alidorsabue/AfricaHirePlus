"""
Vues API candidatures : liste/création, détail, mes candidatures, postuler (public), mise à jour statut, screening, export Excel, prédiction score ML.
"""
import logging
from io import BytesIO
from django.http import HttpResponse
from openpyxl import Workbook
from rest_framework import generics, status, serializers as drf_serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django_filters.rest_framework import DjangoFilterBackend

from .models import Application, MLScore, ApplicationNote, ApplicationAuditLog
from .serializers import (
    ApplicationSerializer,
    ApplicationWriteSerializer,
    ApplicationWithCvSerializer,
    ApplicationStatusUpdateSerializer,
    ApplicationCandidateSerializer,
    ApplicationNoteSerializer,
    ApplicationAuditLogSerializer,
    PublicApplySerializer,
    _validate_uploaded_file,
    CV_ALLOWED_EXTENSIONS,
    CV_ALLOWED_MIME,
    DEFAULT_CV_MAX_SIZE_MB,
    _resolve_max_size,
)
from apps.core.cv_extraction import extract_cv
from apps.core.cv_form_mapper import (
    build_form_data_from_cv_text,
    candidate_to_form_data,
    compute_section_confidence,
    merge_form_data,
)
from .services import (
    submit_application,
    apply_manual_override,
    job_accepts_applications,
    transition_status,
    InvalidStatusTransition,
    withdraw_application,
)
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
    """
    Liste des candidatures du candidat connecté (rôle candidat).
    P10.7 RGPD : retourne `ApplicationCandidateSerializer` qui MASQUE les champs
    internes (scores détaillés, notes recruteur, raisons d'override, etc.).
    """
    serializer_class = ApplicationCandidateSerializer
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


def _get_last_application_with_cv(user, exclude_job_slug: str | None = None):
    """Dernière candidature du candidat disposant d'un CV (fichier ou texte extrait)."""
    qs = Application.objects.filter(
        candidate__user_id=user.id,
    ).select_related('job_offer', 'candidate').order_by('-applied_at')
    if exclude_job_slug:
        qs = qs.exclude(job_offer__slug=exclude_job_slug)
    for app in qs[:20]:
        cand = app.candidate
        if cand and (cand.resume or (cand.raw_cv_text and len(cand.raw_cv_text) >= 50)):
            return app
    return None


class LastCvInfoView(generics.GenericAPIView):
    """
    GET : indique si le candidat peut réutiliser le CV d'une candidature précédente.
    Query optionnel : exclude_job_slug (offre en cours de candidature).
    """
    permission_classes = [IsAuthenticated, IsCandidate]

    def get(self, request):
        exclude_slug = request.query_params.get('exclude_job_slug') or None
        app = _get_last_application_with_cv(request.user, exclude_job_slug=exclude_slug)
        if not app:
            return Response({'available': False})
        cand = app.candidate
        resume_url = None
        if cand.resume:
            resume_url = request.build_absolute_uri(cand.resume.url)
        return Response({
            'available': True,
            'resume_url': resume_url,
            'resume_filename': cand.resume.name.split('/')[-1] if cand.resume else None,
            'applied_at': app.applied_at,
            'job_title': app.job_offer.title if app.job_offer_id else None,
            'application_id': app.id,
        })


class ParseCvForApplicationView(generics.GenericAPIView):
    """
    POST : analyse un CV (upload ou dernière candidature) et retourne les champs
    structurés pour pré-remplir le formulaire de candidature.

    - multipart avec champ `resume` : fichier CV à analyser
    - ou JSON/form `use_last_cv=true` (+ optionnel `exclude_job_slug`)
    """
    permission_classes = [IsAuthenticated, IsCandidate]

    def post(self, request):
        try:
            return self._parse_cv(request)
        except Exception as e:
            logger.exception("ParseCvForApplicationView: erreur inattendue user=%s", request.user.id)
            return Response(
                {'detail': f'Erreur lors de l\'analyse du CV : {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _parse_cv(self, request):
        use_last = str(request.data.get('use_last_cv', '')).lower() in ('1', 'true', 'yes')
        exclude_slug = request.data.get('exclude_job_slug') or None
        resume_file = request.FILES.get('resume')
        warnings: list[str] = []
        resume_url = None
        resume_filename = None
        source = 'upload'
        parsed_confidence: dict[str, float] = {}

        if use_last:
            source = 'last_application'
            app = _get_last_application_with_cv(request.user, exclude_job_slug=exclude_slug)
            if not app:
                return Response(
                    {'detail': 'Aucun CV de candidature précédente trouvé.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            cand = app.candidate
            profile_data = candidate_to_form_data(cand)
            raw_text = (cand.raw_cv_text or '').strip()
            if not raw_text and cand.resume:
                name = cand.resume.name or ''
                try:
                    with cand.resume.open('rb') as f:
                        extraction = extract_cv(
                            f, filename=name, content_type='', allow_ocr=False,
                        )
                    raw_text = extraction.text or ''
                    warnings.extend(extraction.warnings or [])
                except Exception as e:
                    logger.warning("ParseCvForApplicationView: lecture CV stocké échouée: %s", e)
                    warnings.append(f"Impossible de relire le fichier CV : {e}")
            if raw_text and len(raw_text) >= 50:
                parsed_form = build_form_data_from_cv_text(raw_text)
                form_data = merge_form_data(profile_data, parsed_form)
                meta = form_data.pop('parsed_meta', {})
                parsed_confidence = meta.get('confidence') or {}
                warnings.extend(meta.get('warnings') or [])
            else:
                form_data = profile_data
                form_data.pop('parsed_meta', None)
                if not cand.resume:
                    warnings.append("Texte CV indisponible — données du profil uniquement.")
            if cand.resume:
                resume_url = request.build_absolute_uri(cand.resume.url)
                resume_filename = cand.resume.name.split('/')[-1]
        elif resume_file:
            try:
                _validate_uploaded_file(
                    resume_file,
                    field_label='CV',
                    max_bytes=_resolve_max_size('CV_MAX_SIZE_MB', DEFAULT_CV_MAX_SIZE_MB),
                    allowed_extensions=CV_ALLOWED_EXTENSIONS,
                    allowed_mime=CV_ALLOWED_MIME,
                )
            except drf_serializers.ValidationError as e:
                return Response({'detail': e.detail}, status=status.HTTP_400_BAD_REQUEST)

            name = getattr(resume_file, 'name', '') or ''
            ct = getattr(resume_file, 'content_type', '') or ''
            extraction = extract_cv(
                resume_file, filename=name, content_type=ct, allow_ocr=False,
            )
            if hasattr(resume_file, 'seek'):
                try:
                    resume_file.seek(0)
                except Exception:
                    pass
            warnings.extend(extraction.warnings or [])
            raw_text = extraction.text or ''
            if len(raw_text) < 50:
                return Response(
                    {
                        'detail': (
                            'Impossible d\'extraire suffisamment de texte du CV. '
                            'Essayez un PDF texte ou un document Word.'
                        ),
                        'warnings': warnings,
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            form_data = build_form_data_from_cv_text(raw_text)
            meta = form_data.pop('parsed_meta', {})
            parsed_confidence = meta.get('confidence') or {}
            warnings.extend(meta.get('warnings') or [])
            resume_filename = name
        else:
            return Response(
                {'detail': 'Envoyez un fichier CV (resume) ou use_last_cv=true.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        section_confidence = compute_section_confidence(form_data, parsed_confidence, source)

        return Response({
            'source': source,
            'form_data': form_data,
            'section_confidence': section_confidence,
            'resume_url': resume_url,
            'resume_filename': resume_filename,
            'warnings': warnings,
        })


class ApplicationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Détail, modification et suppression d'une candidature (scope tenant).
    P10.1 : GET utilise le sérializer de lecture complet ; PATCH/PUT utilisent
    le `ApplicationWriteSerializer` (scores / overrides en read-only).
    """
    permission_classes = [IsTenantOrSuperAdmin]

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return ApplicationWriteSerializer
        return ApplicationSerializer

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
    """Postuler à une offre (connexion requise). Profil candidat lié au compte.
    P10.8 — throttle `public_apply` (10/heure par défaut)."""
    serializer_class = PublicApplySerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'public_apply'

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
    """
    Mise à jour manuelle du statut (workflow contrôlé par machine d'état).
    Toute transition est validée + tracée dans ApplicationAuditLog.
    """
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
        reason = (request.data.get('reason') or '').strip()
        # Super-admin peut forcer (utile pour corrections data), recruteur classique non
        force = bool(getattr(request.user, 'is_super_admin', False))
        try:
            transition_status(
                app, new_status, actor=request.user, reason=reason, request=request, force=force,
            )
        except InvalidStatusTransition as e:
            return Response(
                {'status': f'Transition interdite : {e.from_status} → {e.to_status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        app.refresh_from_db()
        if new_status == Application.Status.REJECTED:
            try:
                send_rejection_notification(
                    company=app.job_offer.company,
                    candidate_name=app.candidate.get_full_name(),
                    candidate_email=app.candidate.email,
                    job_title=app.job_offer.title,
                )
            except Exception:
                logger.warning("rejection email failed for app=%s", app.pk, exc_info=True)
        return Response(ApplicationSerializer(app).data)


class MyApplicationWithdrawView(generics.GenericAPIView):
    """
    POST /applications/<id>/withdraw/  (candidat uniquement)
    Permet au candidat connecté de retirer sa candidature. Trace dans l'audit log.
    """
    permission_classes = [IsAuthenticated, IsCandidate]

    def post(self, request, pk):
        app = Application.objects.select_related('job_offer', 'candidate').filter(
            pk=pk, candidate__user_id=request.user.id,
        ).first()
        if not app:
            return Response(
                {'detail': 'Candidature introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        reason = (request.data.get('reason') or '').strip()
        try:
            withdraw_application(app, actor=request.user, reason=reason, request=request)
        except InvalidStatusTransition:
            return Response(
                {'detail': 'Cette candidature ne peut plus être retirée (statut final atteint).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        app.refresh_from_db()
        return Response(
            {
                'message': 'Candidature retirée avec succès.',
                'application_id': app.id,
                'status': app.status,
            }
        )


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
        apply_manual_override(
            app, action,
            reason=reason, new_status=new_status, new_score=new_score,
            actor=request.user, request=request,
        )
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
        before = {
            'status': app.status,
            'preselection_score': app.preselection_score,
            'screening_score': app.screening_score,
        }
        updated = run_auto_preselection(app)
        app.refresh_from_db()
        try:
            from .services import record_audit_log
            from .models import ApplicationAuditLog
            record_audit_log(
                app,
                ApplicationAuditLog.Action.RUN_SCREENING,
                actor=request.user,
                payload_before=before,
                payload_after={
                    'status': app.status,
                    'preselection_score': app.preselection_score,
                    'screening_score': app.screening_score,
                    'preselected': bool(updated),
                },
                request=request,
            )
        except Exception:
            logger.warning("audit log run_screening failed app=%s", app.pk, exc_info=True)
        return Response({
            'screening_score': app.screening_score,
            'status': app.status,
            'preselected': updated,
        })


class ApplicationBulkStatusView(generics.GenericAPIView):
    """
    POST /applications/bulk-status/  (recruteur)
    Met à jour le statut de plusieurs candidatures en une requête, via la
    machine d'état (transitions interdites refusées individuellement).

    Payload :
        {
            "application_ids": [1, 2, 3],
            "status": "rejected",
            "reason": "Non retenu après entretien"
        }

    Réponse :
        {
            "updated": [...ids],
            "errors": [{"id": 2, "detail": "Transition interdite ..."}],
        }
    """
    permission_classes = [IsTenantOrSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'bulk_status'

    def get_queryset(self):
        qs = Application.objects.select_related('job_offer')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs

    def post(self, request):
        ids = request.data.get('application_ids') or []
        new_status = request.data.get('status')
        reason = (request.data.get('reason') or '').strip()
        if not isinstance(ids, list) or not ids:
            return Response(
                {'application_ids': 'Liste d\'IDs requise.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_status not in dict(Application.Status.choices):
            return Response({'status': 'Statut invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ids = [int(x) for x in ids]
        except (TypeError, ValueError):
            return Response({'application_ids': 'IDs invalides.'}, status=status.HTTP_400_BAD_REQUEST)
        # Limite de sécurité (anti-DoS)
        if len(ids) > 500:
            return Response(
                {'application_ids': 'Maximum 500 candidatures par appel.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        force = bool(getattr(request.user, 'is_super_admin', False))
        qs = self.get_queryset().filter(pk__in=ids)
        updated, errors = [], []
        for app in qs:
            try:
                transition_status(
                    app, new_status, actor=request.user,
                    reason=reason, request=request, force=force,
                )
                updated.append(app.pk)
            except InvalidStatusTransition as e:
                errors.append({'id': app.pk, 'detail': f'{e.from_status} → {e.to_status} interdit.'})
            except Exception as exc:
                logger.exception("bulk-status: failure for app_id=%s", app.pk)
                errors.append({'id': app.pk, 'detail': str(exc)})
        return Response({'updated': updated, 'errors': errors})


class ApplicationPredictScoreView(generics.GenericAPIView):
    """
    POST /applications/{id}/predict-score/
    Extrait les features, applique le modèle ML, enregistre MLScore et retourne le score.
    Traçabilité : model_version, date de prédiction, logs et audit trail.
    P10.8 — throttle 'predict_score' (120/heure par défaut).
    """
    permission_classes = [IsTenantOrSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'predict_score'

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
            # P10.5 : cap à 20 prédictions par candidature pour éviter l'explosion
            # de la table sur des appels en boucle.
            try:
                from django.conf import settings as _s
                cap = int(getattr(_s, 'MLSCORE_MAX_PER_APPLICATION', 20))
                older = MLScore.objects.filter(application_id=app.pk).order_by('-created_at')[cap:]
                older_ids = [m.pk for m in older]
                if older_ids:
                    MLScore.objects.filter(pk__in=older_ids).delete()
            except Exception:
                logger.warning("MLScore cap cleanup failed app=%s", app.pk, exc_info=True)
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
    """Export Excel des candidatures (filtré par statut optionnel). Throttle 'export'."""
    permission_classes = [IsTenantOrSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'export'

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


class ApplicationNoteListCreateView(generics.ListCreateAPIView):
    """
    Notes internes d'une candidature (recruteur uniquement).
    GET/POST /applications/<application_id>/notes/
    """
    serializer_class = ApplicationNoteSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        application_id = self.kwargs['application_id']
        qs = ApplicationNote.objects.select_related('author', 'application__job_offer').filter(
            application_id=application_id,
        )
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs

    def _get_application(self):
        qs = Application.objects.select_related('job_offer')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(job_offer__company_id=company_id)
        return qs.filter(pk=self.kwargs['application_id']).first()

    def perform_create(self, serializer):
        app = self._get_application()
        if not app:
            raise generics.Http404
        note = serializer.save(application=app, author=self.request.user)
        try:
            from .services import record_audit_log
            record_audit_log(
                app,
                ApplicationAuditLog.Action.NOTE_UPDATED,
                actor=self.request.user,
                payload_after={'note_id': note.pk, 'is_pinned': note.is_pinned},
                request=self.request,
            )
        except Exception:
            logger.warning("audit log note_created failed app=%s", app.pk, exc_info=True)


class ApplicationNoteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail / modification / suppression d'une note interne (recruteur)."""
    serializer_class = ApplicationNoteSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = ApplicationNote.objects.select_related('author', 'application__job_offer')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


class ApplicationAuditLogListView(generics.ListAPIView):
    """Lecture du journal d'audit d'une candidature (recruteur)."""
    serializer_class = ApplicationAuditLogSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        application_id = self.kwargs['application_id']
        qs = ApplicationAuditLog.objects.select_related('actor', 'application__job_offer').filter(
            application_id=application_id,
        )
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


class ExportShortlistedExcelView(generics.GenericAPIView):
    """Export Excel des présélectionnés / shortlistés. Throttle 'export'."""
    permission_classes = [IsTenantOrSuperAdmin]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'export'

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
