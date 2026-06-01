"""
Views API du module Tests.

Durcissement v2 :
  P1 — Sécurité :
    - Endpoint candidat dédié `tests/<id>/take/` (CandidateTestSerializer) — JAMAIS de
      correct_answer/options.correct ; vérifie que le candidat a une Application
      éligible sur l'offre liée au test.
    - Verrou anti-modif post-soumission (auto-save / upload / tab-switch bloqués
      si `result.is_finalized`).
    - Vérification du statut Application (SHORTLISTED/INTERVIEW/OFFER) côté candidat.
    - Whitelist MIME + taille max sur upload de fichier.
    - Enregistrement systématique de client_ip / last_seen_ip.

  P4 — Workflow :
    - Expiration auto avant chaque action (start, auto-save, submit).
    - `is_passed` exposé dans le rapport.
    - Notifications email (assignation, soumission, expiration) déléguées au module emails.

  P5 — Anti-triche :
    - Token d'accès UNIQUE par candidat (TestAccessGrant) supporté en plus du
      legacy access_code.
    - Endpoint candidat sert questions dans l'ordre stabilisé (shuffle / pool).
"""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.applications.models import Application
from apps.core.permissions import IsCandidate, IsRecruiterOrAdmin, IsTenantOrSuperAdmin

from .models import (
    Answer,
    CandidateTestResult,
    CorrectorAssignment,
    Question,
    Test,
    TestAccessGrant,
    TestAuditLog,
)
from .permissions import IsCorrectorToken
from .serializers import (
    CandidateQuestionSerializer,
    CandidateTestResultSerializer,
    CandidateTestSerializer,
    CorrectorAssignmentReadSerializer,
    CorrectorAssignmentWriteSerializer,
    CorrectorReviewSerializer,
    CorrectorSessionDetailSerializer,
    CorrectorSessionListSerializer,
    CorrectorTestInfoSerializer,
    SubmitTestAnswersSerializer,
    TestSerializer,
    TestWriteSerializer,
)
from .services import (
    assign_corrector,
    ensure_display_code,
    expire_session_if_needed,
    get_questions_for_session,
    get_visible_sessions_for_corrector,
    manual_review_answer,
    revoke_corrector,
    submit_test_result,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes sécurité — P1
# ---------------------------------------------------------------------------
# Statuts d'Application autorisés à passer / accéder à un test côté candidat.
# Ne pas autoriser APPLIED ou les rejets — un candidat rejeté ne doit plus
# pouvoir entrer dans un test.
CANDIDATE_TEST_ALLOWED_STATUSES = frozenset({
    Application.Status.SHORTLISTED,
    Application.Status.INTERVIEW,
    Application.Status.OFFER,
})

# Whitelist MIME pour upload de fichier réponse — refus de .exe / .bat / .sh / etc.
ALLOWED_ANSWER_FILE_MIME_PREFIXES = (
    'application/pdf',
    'application/vnd.openxmlformats-officedocument',  # docx, xlsx, pptx
    'application/vnd.ms-',                              # doc, xls, ppt legacy
    'application/msword',
    'application/zip',                                  # archives projet
    'application/x-zip-compressed',
    'application/json',
    'application/octet-stream',                         # fichiers data (.pbix, .csv, etc.)
    'text/',                                            # texte, csv, md, code
    'image/',                                           # screenshots
)
ALLOWED_ANSWER_FILE_EXTENSIONS = frozenset({
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.csv', '.md', '.json', '.zip', '.tar', '.gz',
    '.py', '.js', '.ts', '.java', '.cpp', '.c', '.cs', '.go', '.rb', '.rs', '.php',
    '.html', '.css', '.sql', '.r', '.ipynb',
    '.png', '.jpg', '.jpeg', '.gif', '.webp',
    '.pbix', '.twbx',  # Power BI / Tableau
})
DENIED_ANSWER_FILE_EXTENSIONS = frozenset({
    '.exe', '.bat', '.cmd', '.sh', '.ps1', '.msi', '.com', '.scr', '.vbs', '.jar', '.dll',
})
MAX_ANSWER_FILE_BYTES = 25 * 1024 * 1024  # 25 Mo


# ---------------------------------------------------------------------------
# Helpers transverses
# ---------------------------------------------------------------------------
def _client_ip(request) -> str | None:
    """Récupère l'IP réelle du client (X-Forwarded-For prioritaire)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def _ensure_candidate_can_take(app: Application, test: Test, request) -> Response | None:
    """
    Validation P1 commune à toutes les actions candidat (start, auto-save, upload, tab-switch, submit).

    Retourne None si OK, sinon une Response d'erreur.
    """
    user = request.user
    if getattr(user, 'is_candidate', False):
        if not app.candidate or app.candidate.user_id != user.id:
            return Response(
                {'detail': 'Candidature non liée à ce compte candidat.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if app.status not in CANDIDATE_TEST_ALLOWED_STATUSES:
            return Response(
                {
                    'detail': (
                        'Vous ne pouvez passer ce test qu\'une fois shortlisté(e). '
                        f'Statut actuel : {app.status}.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
    company_id = user.get_company_id()
    if company_id is not None and app.job_offer.company_id != company_id:
        return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
    if test.company_id != app.job_offer.company_id:
        return Response(
            {'detail': "Le test ne correspond pas à l'entreprise de la candidature."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if test.job_offer_id and test.job_offer_id != app.job_offer_id:
        return Response(
            {'detail': "Le test n'est pas lié à l'offre de cette candidature."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _record_session_ip(result: CandidateTestResult, ip: str | None) -> None:
    """Met à jour client_ip (1ère fois) et last_seen_ip (à chaque appel)."""
    if not ip:
        return
    updates = ['last_seen_ip', 'updated_at']
    result.last_seen_ip = ip
    if not result.client_ip:
        result.client_ip = ip
        updates.append('client_ip')
    result.save(update_fields=list(dict.fromkeys(updates)))


# ---------------------------------------------------------------------------
# Gestion des tests (recruteur / admin)
# ---------------------------------------------------------------------------
class TestListCreateView(generics.ListCreateAPIView):
    """Liste / création des tests — recruteur ou super admin uniquement."""

    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        qs = Test.objects.prefetch_related('sections', 'questions')
        # Recruteur : filtrer par sa company. Candidat : ne doit pas accéder ici.
        user = self.request.user
        if getattr(user, 'is_candidate', False):
            return qs.none()
        company_id = user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TestWriteSerializer
        return TestSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning('POST /tests/ validation failed: %s', serializer.errors)
            raise ValidationError(serializer.errors)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        """
        Rattache le test à la company du recruteur (P3 : on ignore systématiquement
        toute valeur `company` fournie par le client pour les recruteurs).
        """
        user = self.request.user
        company_id = user.get_company_id()
        if company_id is None:
            company = serializer.validated_data.get('company')
            company_id = company.pk if company else None
        if company_id is None:
            raise ValidationError({'company': 'Ce champ est requis (ou utilisateur sans entreprise).'})

        access_code = serializer.validated_data.get('access_code') or secrets.token_urlsafe(6)
        serializer.save(company_id=company_id, access_code=access_code)


class TestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail / édition / suppression d'un test — recruteur / admin uniquement.

    P1 : les candidats n'ont AUCUN accès à cette vue (qui exposerait les bonnes
    réponses). Ils doivent utiliser `CandidateTestTakeView` (`/tests/<id>/take/`).
    """
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_candidate', False):
            return Test.objects.none()
        qs = Test.objects.prefetch_related('sections', 'questions')
        company_id = user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return TestWriteSerializer
        return TestSerializer


# ---------------------------------------------------------------------------
# P1 — Endpoint CANDIDAT pour récupérer le test (sans correct_answer)
# ---------------------------------------------------------------------------
class CandidateTestTakeView(APIView):
    """
    Endpoint CANDIDAT pour récupérer un test à passer (questions + métadonnées),
    SANS aucune bonne réponse.

    GET /api/v1/tests/<test_id>/take/?application_id=<id>

    Sécurité (P1) :
    - Le candidat doit être propriétaire de l'Application.
    - L'Application doit être SHORTLISTED / INTERVIEW / OFFER.
    - Le test doit appartenir à la company de l'offre de l'Application.
    - Les questions sont servies via CandidateQuestionSerializer (assaini).
    """

    permission_classes = [IsCandidate]

    def get(self, request, pk: int):
        application_id = request.query_params.get('application_id')
        if not application_id:
            return Response(
                {'detail': 'application_id requis en query string.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        test = Test.objects.filter(pk=pk, is_active=True).first()
        if not test:
            return Response({'detail': 'Test introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        app = (
            Application.objects.filter(pk=application_id)
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        if not app:
            return Response({'detail': 'Candidature introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err

        # Démarre / récupère la session pour figer question_order (P5)
        result, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.PENDING},
        )
        expire_session_if_needed(result)
        if result.is_finalized:
            return Response(
                {'detail': 'Session déjà finalisée — vous ne pouvez plus consulter le test.',
                 'status': result.status},
                status=status.HTTP_403_FORBIDDEN,
            )
        questions = get_questions_for_session(test, result)

        # Sérialisation candidate-safe
        test_payload = CandidateTestSerializer(test).data
        test_payload['questions'] = CandidateQuestionSerializer(questions, many=True).data
        test_payload['session'] = {
            'id': result.id,
            'status': result.status,
            'started_at': result.started_at,
            'seconds_left': self._seconds_left(test, result),
        }
        return Response(test_payload, status=status.HTTP_200_OK)

    @staticmethod
    def _seconds_left(test: Test, result: CandidateTestResult) -> int | None:
        if not test.duration_minutes or not result.started_at:
            return None
        deadline = result.started_at + timedelta(minutes=test.duration_minutes)
        return max(0, int((deadline - timezone.now()).total_seconds()))


# ---------------------------------------------------------------------------
# Attachments question (recruteur)
# ---------------------------------------------------------------------------
class QuestionAttachmentUploadView(APIView):
    permission_classes = [IsRecruiterOrAdmin]

    def post(self, request, test_id, question_id):
        test = Test.objects.filter(pk=test_id).first()
        if not test:
            return Response({'detail': 'Test introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and test.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
        question = Question.objects.filter(pk=question_id, test_id=test_id).first()
        if not question:
            return Response({'detail': 'Question introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'Aucun fichier fourni (champ "file").'}, status=status.HTTP_400_BAD_REQUEST)
        question.attachment = file_obj
        question.save(update_fields=['attachment', 'updated_at'])
        url = question.attachment.url if question.attachment else None
        return Response({'attachment': url, 'question_id': question.id}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Candidat : sessions + tests disponibles
# ---------------------------------------------------------------------------
class MyTestSessionsView(APIView):
    permission_classes = [IsCandidate]

    def get(self, request):
        qs = (
            CandidateTestResult.objects.filter(application__candidate__user_id=request.user.id)
            .select_related('test', 'application__job_offer')
            .order_by('-created_at')
        )
        data = [
            {
                'id': r.id,
                'application_id': r.application_id,
                'test_id': r.test_id,
                'test_title': r.test.title,
                'job_title': r.application.job_offer.title if r.application.job_offer else None,
                'status': r.status,
                'score': r.score,
                'max_score': r.max_score,
                'is_passed': r.is_passed,
                'pending_review_points': r.pending_review_points,
                'started_at': r.started_at,
                'submitted_at': r.submitted_at,
                'is_completed': r.is_completed,
            }
            for r in qs
        ]
        return Response(data, status=status.HTTP_200_OK)


class MyAvailableTestsView(APIView):
    """Liste des tests disponibles pour le candidat connecté (par candidature éligible)."""
    permission_classes = [IsCandidate]

    def get(self, request):
        # P1 : ne lister que les Applications éligibles (shortlisted+) et P6 : limiter les requêtes
        eligible_apps = (
            Application.objects.filter(
                candidate__user_id=request.user.id,
                status__in=list(CANDIDATE_TEST_ALLOWED_STATUSES),
            )
            .select_related('job_offer')
            .prefetch_related('test_results')
        )
        company_ids = {app.job_offer.company_id for app in eligible_apps if app.job_offer_id}
        if not company_ids:
            return Response([], status=status.HTTP_200_OK)
        tests_by_company: dict[int, list[Test]] = {}
        for t in Test.objects.filter(company_id__in=company_ids, is_active=True).only(
            'id', 'title', 'duration_minutes', 'job_offer_id', 'company_id', 'passing_score',
        ):
            tests_by_company.setdefault(t.company_id, []).append(t)
        result = []
        for app in eligible_apps:
            company_id = app.job_offer.company_id
            existing = {r.test_id: r for r in app.test_results.all()}
            for t in tests_by_company.get(company_id, []):
                if t.job_offer_id and t.job_offer_id != app.job_offer_id:
                    continue
                session = existing.get(t.id)
                result.append({
                    'application_id': app.id,
                    'job_title': app.job_offer.title if app.job_offer else None,
                    'test_id': t.id,
                    'test_title': t.title,
                    'duration_minutes': t.duration_minutes,
                    'session_id': session.id if session else None,
                    'status': session.status if session else 'pending',
                    'is_completed': session.is_completed if session else False,
                    'is_passed': session.is_passed if session else None,
                })
        return Response(result, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Résultats — recruteur
# ---------------------------------------------------------------------------
class CandidateTestResultListCreateView(generics.ListCreateAPIView):
    serializer_class = CandidateTestResultSerializer
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_candidate', False):
            return CandidateTestResult.objects.none()
        qs = CandidateTestResult.objects.select_related(
            'application', 'test', 'application__job_offer',
        )
        company_id = user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


class CandidateTestResultDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CandidateTestResultSerializer
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'is_candidate', False):
            return CandidateTestResult.objects.none()
        qs = CandidateTestResult.objects.select_related('application', 'test')
        company_id = user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


# ---------------------------------------------------------------------------
# Vérification d'accès via email + code (legacy) OU token unique (P5)
# ---------------------------------------------------------------------------
class CheckTestAccessView(APIView):
    """
    Deux modes d'accès :
      1) (P5 préféré) `{ token }` → résolution via TestAccessGrant.
      2) (legacy)      `{ email, code, test_id }` → résolution via Test.access_code partagé.
    """
    permission_classes = [IsCandidate]

    def post(self, request):
        token = (request.data.get('token') or '').strip()

        # Mode P5 : token unique
        if token:
            grant = (
                TestAccessGrant.objects
                .filter(token=token, is_revoked=False)
                .select_related('test', 'application__candidate__user', 'application__job_offer')
                .first()
            )
            if not grant or not grant.test.is_active:
                return Response({'detail': 'Token invalide ou test inactif.'}, status=status.HTTP_404_NOT_FOUND)
            if grant.expires_at and grant.expires_at < timezone.now():
                return Response({'detail': 'Token expiré.'}, status=status.HTTP_403_FORBIDDEN)
            if grant.application.candidate.user_id and grant.application.candidate.user_id != request.user.id:
                return Response({'detail': 'Ce token n\'appartient pas à votre compte.'}, status=status.HTTP_403_FORBIDDEN)
            if grant.application.status not in CANDIDATE_TEST_ALLOWED_STATUSES:
                return Response(
                    {'detail': 'Votre candidature n\'est pas éligible pour passer ce test.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not grant.used_at:
                grant.used_at = timezone.now()
                grant.save(update_fields=['used_at', 'updated_at'])
            return Response(
                {'application_id': grant.application_id, 'test_id': grant.test_id},
                status=status.HTTP_200_OK,
            )

        # Mode legacy
        email = (request.data.get('email') or '').strip().lower()
        code = (request.data.get('code') or '').strip()
        test_id = request.data.get('test_id')
        if not email or not code or not test_id:
            return Response(
                {'detail': 'email, code et test_id sont requis (ou token).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            test_id = int(test_id)
        except (TypeError, ValueError):
            return Response({'detail': 'test_id invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        test = Test.objects.filter(pk=test_id, is_active=True).select_related('job_offer').first()
        if not test or not test.job_offer_id:
            return Response({'detail': 'Test introuvable ou sans offre liée.'}, status=status.HTTP_404_NOT_FOUND)
        if not test.access_code or secrets.compare_digest(test.access_code, code) is False:
            return Response({'detail': 'Code d\'accès invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        app = (
            Application.objects.filter(
                job_offer_id=test.job_offer_id,
                status__in=list(CANDIDATE_TEST_ALLOWED_STATUSES),
                candidate__email__iexact=email,
            )
            .select_related('candidate__user')
            .first()
        )
        if not app:
            return Response(
                {'detail': 'Aucune candidature éligible trouvée pour cet email et cette offre.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if app.candidate.user_id and app.candidate.user_id != request.user.id:
            return Response(
                {'detail': 'Cet email ne correspond pas à votre compte candidat.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({'application_id': app.id, 'test_id': test.id}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Session : start / auto-save / tab-switch / upload / submit
# ---------------------------------------------------------------------------
def _resolve_app_and_test(request) -> tuple[Application | None, Test | None, Response | None]:
    """Récupère app + test depuis le payload, ou retourne une Response d'erreur."""
    app_id = request.data.get('application_id')
    test_id = request.data.get('test_id')
    if not app_id or not test_id:
        return None, None, Response(
            {'detail': 'application_id et test_id sont requis.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    app = (
        Application.objects.filter(pk=app_id)
        .select_related('job_offer', 'candidate__user').first()
    )
    test = Test.objects.filter(pk=test_id).first()
    if not app or not test:
        return None, None, Response(
            {'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND,
        )
    return app, test, None


class StartTestSessionView(APIView):
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        app, test, err = _resolve_app_and_test(request)
        if err is not None:
            return err
        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app, test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        expire_session_if_needed(result)
        if result.is_finalized:
            return Response(
                {'detail': 'Session déjà finalisée.', 'status': result.status},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        if not result.started_at:
            result.started_at = now
            result.status = CandidateTestResult.Status.IN_PROGRESS
            result.save(update_fields=['started_at', 'status', 'updated_at'])

        _record_session_ip(result, _client_ip(request))

        seconds_left = None
        if test.duration_minutes:
            deadline = result.started_at + timedelta(minutes=test.duration_minutes)
            seconds_left = max(0, int((deadline - now).total_seconds()))

        return Response(
            {
                'result_id': result.id,
                'status': result.status,
                'started_at': result.started_at,
                'seconds_left': seconds_left,
            },
            status=status.HTTP_200_OK,
        )


class AutoSaveTestAnswersView(APIView):
    """Auto-save des réponses pendant le test (toutes les X secondes)."""
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        app, test, err = _resolve_app_and_test(request)
        if err is not None:
            return err
        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err
        answers = request.data.get('answers') or {}
        if not isinstance(answers, dict):
            return Response({'detail': 'answers doit être un objet.'}, status=status.HTTP_400_BAD_REQUEST)

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app, test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        expire_session_if_needed(result)
        # P1 — verrou anti-modif post-soumission
        if result.is_finalized:
            return Response(
                {'detail': 'Session finalisée — modifications refusées.', 'status': result.status},
                status=status.HTTP_403_FORBIDDEN,
            )

        result.answers = answers
        if not result.started_at:
            result.started_at = timezone.now()
        if result.status == CandidateTestResult.Status.PENDING:
            result.status = CandidateTestResult.Status.IN_PROGRESS
        result.save(update_fields=['answers', 'started_at', 'status', 'updated_at'])

        _record_session_ip(result, _client_ip(request))
        return Response({'detail': 'Auto-save OK.'}, status=status.HTTP_200_OK)


class TabSwitchView(APIView):
    """Anti-triche basique : incrémente tab_switch_count."""
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        app, test, err = _resolve_app_and_test(request)
        if err is not None:
            return err
        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app, test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        if result.is_finalized:
            # Ne pas polluer les résultats après soumission, mais répondre 200
            return Response(
                {
                    'tab_switch_count': result.tab_switch_count,
                    'is_flagged': result.is_flagged,
                    'detail': 'Session finalisée — événement ignoré.',
                },
                status=status.HTTP_200_OK,
            )
        result.tab_switch_count += 1
        if result.tab_switch_count > 3:
            result.is_flagged = True
        result.save(update_fields=['tab_switch_count', 'is_flagged', 'updated_at'])
        _record_session_ip(result, _client_ip(request))
        return Response(
            {'tab_switch_count': result.tab_switch_count, 'is_flagged': result.is_flagged},
            status=status.HTTP_200_OK,
        )


class UploadAnswerFileView(APIView):
    """
    Upload d'un fichier réponse (questions FILE_UPLOAD).

    Sécurité (P1) :
    - Whitelist d'extensions (.exe / .bat / .sh refusés).
    - Whitelist de types MIME.
    - Taille max 25 Mo.
    - Vérifications standard (multi-tenant, rôle, statut application).
    """
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        app, test, err = _resolve_app_and_test(request)
        if err is not None:
            return err
        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err

        question_id = request.data.get('question_id')
        upload = request.FILES.get('file')
        if not question_id or not upload:
            return Response(
                {'detail': 'question_id et file sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question = Question.objects.filter(pk=question_id, test_id=test.id).first()
        if not question:
            return Response({'detail': 'Question introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        if question.question_type != Question.QuestionType.FILE_UPLOAD:
            return Response(
                {'detail': 'Cette question n\'accepte pas de fichier.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validation sécurité fichier (P1)
        if upload.size and upload.size > MAX_ANSWER_FILE_BYTES:
            return Response(
                {'detail': f'Fichier trop volumineux (max {MAX_ANSWER_FILE_BYTES // (1024*1024)} Mo).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        name_lower = (upload.name or '').lower()
        ext = name_lower[name_lower.rfind('.'):] if '.' in name_lower else ''
        if ext in DENIED_ANSWER_FILE_EXTENSIONS:
            return Response(
                {'detail': f'Extension {ext} interdite pour des raisons de sécurité.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if ext and ext not in ALLOWED_ANSWER_FILE_EXTENSIONS:
            return Response(
                {'detail': f'Extension {ext} non autorisée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type = (upload.content_type or '').lower()
        if content_type and not content_type.startswith(ALLOWED_ANSWER_FILE_MIME_PREFIXES):
            return Response(
                {'detail': f'Type MIME non autorisé ({content_type}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session, _ = CandidateTestResult.objects.get_or_create(
            application=app, test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        if session.is_finalized:
            return Response(
                {'detail': 'Session finalisée — upload refusé.', 'status': session.status},
                status=status.HTTP_403_FORBIDDEN,
            )

        answer, _ = Answer.objects.get_or_create(
            session=session, question=question,
            defaults={'pending_manual_review': True},
        )
        answer.file = upload
        answer.pending_manual_review = True
        answer.save(update_fields=['file', 'pending_manual_review', 'updated_at'])
        _record_session_ip(session, _client_ip(request))
        return Response(
            {'detail': 'Fichier réponse uploadé.', 'filename': upload.name},
            status=status.HTTP_200_OK,
        )


class SubmitTestAnswersView(generics.GenericAPIView):
    """Soumission finale + scoring."""
    serializer_class = SubmitTestAnswersSerializer
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        app = (
            Application.objects.filter(pk=ser.validated_data['application_id'])
            .select_related('job_offer', 'candidate__user').first()
        )
        test = Test.objects.filter(pk=ser.validated_data['test_id']).prefetch_related('questions').first()
        if not app or not test:
            return Response({'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        err = _ensure_candidate_can_take(app, test, request)
        if err is not None:
            return err

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app, test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        expire_session_if_needed(result)
        if result.status == CandidateTestResult.Status.EXPIRED:
            return Response(
                {'detail': 'Temps de test écoulé. Soumission refusée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result.is_finalized:
            return Response(
                {'detail': 'Session déjà soumise — nouvelle soumission refusée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not result.started_at:
            result.started_at = timezone.now()
            result.status = CandidateTestResult.Status.IN_PROGRESS
            result.save(update_fields=['started_at', 'status', 'updated_at'])

        scored_result = submit_test_result(
            app, test, ser.validated_data['answers'],
            client_ip=_client_ip(request),
        )

        # P4 — Notifications email (best-effort, ne pas bloquer la réponse)
        try:
            from apps.emails.services import send_test_submitted_notification
            send_test_submitted_notification(scored_result)
        except Exception as e:
            logger.warning('Notification soumission test échouée : %s', e)

        return Response(
            {
                'message': 'Résultats enregistrés.',
                'score': scored_result.score,
                'max_score': scored_result.max_score,
                'pending_review_points': scored_result.pending_review_points,
                'is_passed': scored_result.is_passed,
                'status': scored_result.status,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Exports & rapports
# ---------------------------------------------------------------------------
class ExportTestResultsExcelView(generics.GenericAPIView):
    """Export Excel des résultats de tests."""
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = CandidateTestResult.objects.filter(
            status=CandidateTestResult.Status.SCORED
        ).select_related('application', 'test', 'application__candidate', 'application__job_offer')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs

    def get(self, request):
        qs = self.get_queryset()
        wb = Workbook()
        ws = wb.active
        ws.title = 'Résultats tests'
        ws.append([
            'Candidat', 'Email', 'Offre', 'Test',
            'Score', 'Max', 'Pending review', 'Réussi ?',
            'Soumis le', 'Tab switches', 'Suspect ?', 'IP',
        ])
        for r in qs:
            ws.append([
                r.application.candidate.get_full_name(),
                r.application.candidate.email,
                r.application.job_offer.title,
                r.test.title,
                float(r.score or 0),
                float(r.max_score or 0),
                float(r.pending_review_points or 0),
                'Oui' if r.is_passed else ('Non' if r.is_passed is False else 'N/A'),
                r.submitted_at.isoformat() if r.submitted_at else '',
                r.tab_switch_count,
                'Oui' if r.is_flagged else 'Non',
                r.client_ip or '',
            ])
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="resultats_tests.xlsx"'
        return response


class CandidateTestReportView(generics.RetrieveAPIView):
    """Rapport JSON détaillé pour un résultat de test (vue recruteur)."""
    permission_classes = [IsRecruiterOrAdmin]

    def get(self, request, *args, **kwargs):
        from .services import build_test_report

        pk = kwargs.get('pk')
        result = (
            CandidateTestResult.objects.select_related('test', 'application__job_offer')
            .filter(pk=pk).first()
        )
        if not result:
            return Response({'detail': 'Résultat introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and result.application.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        report = build_test_report(result.test, result.answers or {})
        payload = {
            'id': result.id,
            'application_id': result.application_id,
            'test_id': result.test_id,
            'status': result.status,
            'score': float(result.score or 0),
            'max_score': float(result.max_score or 0),
            'pending_review_points': float(result.pending_review_points or 0),
            'is_passed': result.is_passed,
            'tab_switch_count': result.tab_switch_count,
            'is_flagged': result.is_flagged,
            'started_at': result.started_at,
            'submitted_at': result.submitted_at,
            'client_ip': result.client_ip,
            'report': report,
        }
        return Response(payload, status=status.HTTP_200_OK)


class CandidateTestReportPDFView(APIView):
    """Génération d'un rapport PDF (vue recruteur)."""
    permission_classes = [IsRecruiterOrAdmin]

    def get(self, request, *args, **kwargs):
        from .services import build_test_report

        pk = kwargs.get('pk')
        result = (
            CandidateTestResult.objects.select_related(
                'test', 'application__candidate', 'application__job_offer',
            ).filter(pk=pk).first()
        )
        if not result:
            return Response({'detail': 'Résultat introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and result.application.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        report = build_test_report(result.test, result.answers or {})

        buffer = BytesIO()
        p = pdf_canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        x_margin = 40
        y = height - 50
        candidate = result.application.candidate
        job = result.application.job_offer

        def line(text: str, font_size: int = 10, bold: bool = False):
            nonlocal y
            if y < 80:
                p.showPage()
                y = height - 50
            p.setFont('Helvetica-Bold' if bold else 'Helvetica', font_size)
            p.drawString(x_margin, y, text)
            y -= font_size + 4

        line('AfricaHire+ - Rapport de test candidat', font_size=14, bold=True)
        y -= 10
        line(f'Candidat : {candidate.get_full_name()} ({candidate.email})', font_size=11)
        line(f'Offre : {job.title}', font_size=11)
        line(f'Test : {result.test.title}', font_size=11)
        line(f'Statut : {result.status}', font_size=10)
        line(
            f'Score global : {report.get("score_total", 0)} / {report.get("max_score", 0)}',
            font_size=11, bold=True,
        )
        pending = report.get('pending_review_points', 0)
        if pending:
            line(
                f'Points en attente de révision manuelle : {pending}',
                font_size=10, bold=True,
            )
        if result.test.passing_score is not None:
            verdict = 'RÉUSSI' if result.is_passed else 'ÉCHEC' if result.is_passed is False else 'EN ATTENTE'
            line(f'Seuil de réussite : {result.test.passing_score} → {verdict}', font_size=10)
        suspicion = 'FLAGGED' if result.is_flagged else 'Normal'
        line(
            f'Suspicion : {suspicion} (tab switches = {result.tab_switch_count})',
            font_size=10,
        )
        if result.client_ip:
            line(f'IP candidat : {result.client_ip}', font_size=9)
        y -= 10

        sections = report.get('sections') or {}
        if sections:
            line('Score par section', font_size=12, bold=True)
            for _, sec in sections.items():
                line(f"- {sec.get('title')}: {sec.get('score')} / {sec.get('max_score')}", font_size=10)
            y -= 6
        competencies = report.get('competencies') or {}
        if competencies:
            line('Score par compétence', font_size=12, bold=True)
            for _, comp in competencies.items():
                line(f"- {comp.get('name')}: {comp.get('score')} / {comp.get('max_score')}", font_size=10)
            y -= 6

        p.showPage()
        p.save()
        pdf = buffer.getvalue()
        buffer.close()

        filename = f"rapport_test_candidat_{result.id}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ---------------------------------------------------------------------------
# P6 — Review manuelle d'une réponse (open_text / code / file)
# ---------------------------------------------------------------------------
class ManualReviewAnswerView(APIView):
    """
    Endpoint recruteur : noter manuellement une réponse open_text / code / file.

    POST /api/v1/tests/answers/<answer_id>/review/
    Body: { score: 7.5, is_correct: true, reason: "Bonne approche" }
    """
    permission_classes = [IsRecruiterOrAdmin]

    def post(self, request, answer_id: int):
        from decimal import Decimal as _D

        answer = (
            Answer.objects.select_related(
                'question', 'session__application__job_offer',
            ).filter(pk=answer_id).first()
        )
        if not answer:
            return Response({'detail': 'Réponse introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if (
            company_id is not None
            and answer.session.application.job_offer.company_id != company_id
        ):
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        score = request.data.get('score')
        is_correct = request.data.get('is_correct')
        reason = (request.data.get('reason') or '').strip()
        if score is None:
            return Response({'detail': 'score requis.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            score_value = _D(str(score))
        except Exception:
            return Response({'detail': 'score invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        manual_review_answer(
            answer,
            score_obtained=score_value,
            is_correct=is_correct,
            actor=request.user,
            reason=reason,
            client_ip=_client_ip(request),
        )
        return Response(
            {
                'score_obtained': float(answer.score_obtained or 0),
                'is_correct': answer.is_correct,
                'pending_manual_review': answer.pending_manual_review,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================================
# P8 — CORRECTEUR EXTERNE
# ===========================================================================
#
# Deux familles d'endpoints :
#   A) Recruteur (JWT) : créer / lister / révoquer une assignation correcteur.
#      Permet aussi de restreindre le périmètre (toutes les sessions OU une
#      sous-liste de candidatures).
#   B) Correcteur (token magique, sans compte) : consulter et noter de manière
#      anonymisée. JAMAIS d'info identifiante candidate.

# --- Recruteur : CRUD assignations correcteur --------------------------------
class TestCorrectorAssignmentListCreateView(APIView):
    """
    Recruteur :
      - GET  /api/v1/tests/<test_id>/correctors/  → liste des correcteurs du test.
      - POST /api/v1/tests/<test_id>/correctors/  → assigner un nouveau correcteur
        (envoi automatique de l'email d'invitation).

    Body POST :
    {
      "email": "corrector@external.com",
      "full_name": "Jean Correcteur",
      "assigned_application_ids": [1, 2, 3],   // optionnel — si absent ou null = tous
      "expires_in_days": 30                    // optionnel
    }
    """
    permission_classes = [IsRecruiterOrAdmin]

    def _get_test(self, request, test_id):
        test = Test.objects.filter(pk=test_id).select_related('company', 'job_offer').first()
        if not test:
            return None, Response({'detail': 'Test introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and test.company_id != company_id:
            return None, Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
        return test, None

    def get(self, request, test_id):
        test, err = self._get_test(request, test_id)
        if err is not None:
            return err
        qs = (
            CorrectorAssignment.objects
            .filter(test=test)
            .prefetch_related('assigned_applications')
            .order_by('-created_at')
        )
        return Response(
            CorrectorAssignmentReadSerializer(qs, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, test_id):
        test, err = self._get_test(request, test_id)
        if err is not None:
            return err
        ser = CorrectorAssignmentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # `assigned_application_ids` : None (absent) → all_candidates=True
        #                             liste (même vide) → restriction explicite
        app_ids = data.get('assigned_application_ids', None)
        if 'assigned_application_ids' in request.data and request.data.get('assigned_application_ids') is None:
            app_ids = None  # null explicite = pas de restriction
        elif 'assigned_application_ids' not in request.data:
            app_ids = None  # absent = pas de restriction

        assignment = assign_corrector(
            test,
            email=data['email'],
            assigned_by=request.user,
            full_name=data.get('full_name', ''),
            assigned_application_ids=app_ids,
            expires_in_days=data.get('expires_in_days') or 30,
            client_ip=_client_ip(request),
        )

        # Envoi de l'email d'invitation (best-effort)
        try:
            from apps.emails.services import send_corrector_invitation
            send_corrector_invitation(assignment)
        except Exception as e:
            logger.warning('Email invitation correcteur échoué : %s', e)

        return Response(
            CorrectorAssignmentReadSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class CorrectorAssignmentResendView(APIView):
    """
    Recruteur : renvoyer l'email d'invitation à un correcteur (utile en cas
    de perte de l'email original ou de besoin de relance).

    POST /api/v1/tests/correctors/<id>/resend/
    Body optionnel: { "rotate_token": true }  // régénère un nouveau token
                                              // (invalide l'ancien lien)
    """
    permission_classes = [IsRecruiterOrAdmin]

    def post(self, request, pk: int):
        assignment = (
            CorrectorAssignment.objects
            .filter(pk=pk)
            .select_related('test', 'company')
            .first()
        )
        if not assignment:
            return Response({'detail': 'Assignation introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and assignment.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
        if assignment.is_revoked:
            return Response(
                {'detail': 'Cette assignation est révoquée — créez-en une nouvelle.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rotation optionnelle du token (recommandé si on suspecte une fuite)
        rotate = bool(request.data.get('rotate_token', False))
        if rotate:
            from .models import _generate_corrector_token
            assignment.token = _generate_corrector_token()
            assignment.save(update_fields=['token', 'updated_at'])

        # Envoi de l'email (best-effort, ne bloque pas la réponse)
        try:
            from apps.emails.services import send_corrector_invitation
            send_corrector_invitation(assignment)
        except Exception as e:
            logger.warning('Resend email correcteur échoué : %s', e)
            return Response(
                {'detail': "Email impossible à envoyer pour le moment, réessayez plus tard."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                'detail': 'Email renvoyé.',
                'token_rotated': rotate,
                'corrector': CorrectorAssignmentReadSerializer(assignment).data,
            },
            status=status.HTTP_200_OK,
        )


class CorrectorAssignmentDetailView(APIView):
    """
    Recruteur :
      - PATCH /api/v1/correctors/<id>/  → mettre à jour (re-assigner candidats,
        prolonger l'expiration). Body identique à POST.
      - DELETE /api/v1/correctors/<id>/ → révoquer (le token devient invalide).
    """
    permission_classes = [IsRecruiterOrAdmin]

    def _get(self, request, pk):
        a = (
            CorrectorAssignment.objects
            .filter(pk=pk)
            .select_related('test', 'company')
            .first()
        )
        if not a:
            return None, Response({'detail': 'Assignation introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        company_id = request.user.get_company_id()
        if company_id is not None and a.company_id != company_id:
            return None, Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)
        return a, None

    def patch(self, request, pk):
        assignment, err = self._get(request, pk)
        if err is not None:
            return err
        ser = CorrectorAssignmentWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Reuse assign_corrector pour réutiliser la logique de filtrage M2M.
        # On force la même email pour mettre à jour la même assignation.
        app_ids = None
        if 'assigned_application_ids' in request.data:
            value = request.data.get('assigned_application_ids')
            app_ids = value  # peut être None ou liste

        # Si l'email change, on crée une nouvelle assignation (équivalent à
        # créer un nouveau correcteur — l'ancien reste en place pour audit).
        new_email = data.get('email', assignment.email)
        if new_email and new_email.lower() != assignment.email:
            # Création d'une nouvelle assignation
            new_assignment = assign_corrector(
                assignment.test,
                email=new_email,
                assigned_by=request.user,
                full_name=data.get('full_name', ''),
                assigned_application_ids=app_ids,
                expires_in_days=data.get('expires_in_days') or 30,
                client_ip=_client_ip(request),
            )
            return Response(
                CorrectorAssignmentReadSerializer(new_assignment).data,
                status=status.HTTP_200_OK,
            )

        # Mise à jour de l'assignation existante
        if 'full_name' in data:
            assignment.full_name = data['full_name']
        if 'expires_in_days' in data and data['expires_in_days']:
            from datetime import timedelta
            assignment.expires_at = timezone.now() + timedelta(days=int(data['expires_in_days']))
        if 'assigned_application_ids' in request.data:
            if app_ids is None:
                assignment.all_candidates = True
                assignment.assigned_applications.clear()
            else:
                from apps.applications.models import Application
                valid_apps = (
                    Application.objects.filter(
                        pk__in=app_ids,
                        job_offer_id=assignment.test.job_offer_id,
                    ) if assignment.test.job_offer_id else Application.objects.none()
                )
                assignment.all_candidates = False
                assignment.assigned_applications.set(valid_apps)
        assignment.save()
        return Response(
            CorrectorAssignmentReadSerializer(assignment).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        assignment, err = self._get(request, pk)
        if err is not None:
            return err
        revoke_corrector(
            assignment,
            revoked_by=request.user,
            reason=(request.data.get('reason') if hasattr(request, 'data') else '') or '',
            client_ip=_client_ip(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Correcteur (token, sans compte) -----------------------------------------
#
# Toutes ces views désactivent l'authentification DRF par défaut
# (pour éviter qu'un JWT valide ne court-circuite la vérif token) et utilisent
# `IsCorrectorToken` qui attache `request.corrector_assignment`.

class CorrectorAuthCheckView(APIView):
    """
    POST /api/v1/correctors/auth/check/

    Vérifie qu'un token correcteur est valide et retourne le contexte minimal
    nécessaire au frontend (titre du test, job role, scope, nombre de sessions
    à corriger).
    """
    authentication_classes = []
    permission_classes = [IsCorrectorToken]

    def post(self, request):
        a: CorrectorAssignment = request.corrector_assignment
        sessions = get_visible_sessions_for_corrector(a)
        return Response(
            {
                'corrector': {
                    'email': a.email,
                    'full_name': a.full_name,
                    'expires_at': a.expires_at,
                    'scope': 'all_candidates' if a.all_candidates else 'restricted',
                    'assigned_count': (
                        a.assigned_applications.count() if not a.all_candidates else None
                    ),
                },
                'test': CorrectorTestInfoSerializer(a.test).data,
                'sessions_to_review': sessions.count(),
            },
            status=status.HTTP_200_OK,
        )


class CorrectorSessionsListView(APIView):
    """
    GET /api/v1/correctors/sessions/

    Liste anonymisée des sessions à corriger.
    """
    authentication_classes = []
    permission_classes = [IsCorrectorToken]

    def get(self, request):
        from django.db.models import Count, Q
        a: CorrectorAssignment = request.corrector_assignment
        qs = get_visible_sessions_for_corrector(a).annotate(
            pending_answers_count=Count(
                'answer_rows',
                filter=Q(answer_rows__pending_manual_review=True),
            ),
        )

        # Génération paresseuse des display_code pour cette liste
        for result in qs:
            if not result.display_code:
                ensure_display_code(result)
        # Refresh pour s'assurer que display_code est à jour dans la sérialisation
        qs = qs.order_by('-submitted_at', '-id')

        return Response(
            {
                'test': CorrectorTestInfoSerializer(a.test).data,
                'scope': 'all_candidates' if a.all_candidates else 'restricted',
                'sessions': CorrectorSessionListSerializer(qs, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class CorrectorSessionDetailView(APIView):
    """
    GET /api/v1/correctors/sessions/<id>/

    Détail anonymisé : test info + toutes les réponses + correct_answer
    (le correcteur a besoin du corrigé pour noter).
    """
    authentication_classes = []
    permission_classes = [IsCorrectorToken]

    def get(self, request, pk: int):
        a: CorrectorAssignment = request.corrector_assignment
        # Filtrage de sécurité : la session doit appartenir au scope du correcteur
        visible = get_visible_sessions_for_corrector(a).filter(pk=pk).first()
        if not visible:
            return Response(
                {'detail': "Session introuvable ou hors de votre périmètre."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ensure_display_code(visible)
        return Response(
            CorrectorSessionDetailSerializer(visible).data,
            status=status.HTTP_200_OK,
        )


class CorrectorReviewAnswerView(APIView):
    """
    POST /api/v1/correctors/answers/<answer_id>/review/

    Le correcteur note (ou re-note) une réponse — y compris les réponses
    automatiquement corrigées (QCM, true/false, numérique). Toutes les
    modifications sont tracées dans `TestAuditLog` avec
    `action=corrector_review` et `corrector=<assignment>`.

    Body :
    {
      "score": 7.5,           // requis
      "is_correct": true,     // optionnel
      "reason": "Réponse alternative acceptable"   // optionnel
    }
    """
    authentication_classes = []
    permission_classes = [IsCorrectorToken]

    def post(self, request, answer_id: int):
        a: CorrectorAssignment = request.corrector_assignment

        answer = (
            Answer.objects
            .select_related('question', 'session', 'session__application')
            .filter(pk=answer_id)
            .first()
        )
        if not answer:
            return Response(
                {'detail': 'Réponse introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        # La session doit appartenir au scope du correcteur
        visible = get_visible_sessions_for_corrector(a).filter(pk=answer.session_id).first()
        if not visible:
            return Response(
                {'detail': 'Cette réponse est hors de votre périmètre de correction.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ser = CorrectorReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        manual_review_answer(
            answer,
            score_obtained=data['score'],
            is_correct=data.get('is_correct'),
            corrector=a,
            reason=data.get('reason', ''),
            client_ip=_client_ip(request),
        )
        answer.refresh_from_db()
        # On renvoie aussi le score agrégé de la session pour éviter un refetch
        # complet côté UI (les correcteurs notent souvent plusieurs réponses
        # à la suite).
        session = visible
        session.refresh_from_db()
        return Response(
            {
                'answer_id': answer.id,
                'score_obtained': float(answer.score_obtained or 0),
                'is_correct': answer.is_correct,
                'pending_manual_review': answer.pending_manual_review,
                'session_score': float(session.score or 0),
                'session_pending_review_points': float(session.pending_review_points or 0),
                'session_is_passed': session.is_passed,
            },
            status=status.HTTP_200_OK,
        )
