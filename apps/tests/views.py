import logging
from io import BytesIO
from datetime import timedelta
import secrets

from django.http import HttpResponse
logger = logging.getLogger(__name__)
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from rest_framework.exceptions import ValidationError

from .models import Test, Question, CandidateTestResult
from .serializers import (
    TestSerializer,
    TestWriteSerializer,
    CandidateTestResultSerializer,
    SubmitTestAnswersSerializer,
)
from .services import submit_test_result, build_test_report
from apps.applications.models import Application
from apps.core.permissions import IsTenantOrSuperAdmin, IsRecruiterOrAdmin, IsCandidate


class TestListCreateView(generics.ListCreateAPIView):
    """
    Gestion des tests (création / liste) côté recruteur / admin.
    Les candidats ne peuvent pas créer ni modifier les tests.
    """

    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        qs = Test.objects.prefetch_related('sections', 'questions')
        company_id = self.request.user.get_company_id()
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
        """Rattacher le test à l'entreprise du recruteur (ou celle fournie pour super admin) et générer un code d'accès si absent."""
        company_id = self.request.user.get_company_id()
        if company_id is None:
            company = serializer.validated_data.get('company')
            company_id = company.pk if company else None
        if company_id is None:
            raise ValidationError({'company': 'Ce champ est requis (ou utilisateur sans entreprise).'})

        access_code = serializer.validated_data.get('access_code') or secrets.token_urlsafe(6)
        serializer.save(company_id=company_id, access_code=access_code)


class TestDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        qs = Test.objects.prefetch_related('sections', 'questions')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return TestWriteSerializer
        return TestSerializer


class QuestionAttachmentUploadView(APIView):
    """
    Upload du fichier ressource (attachment) d'une question par le recruteur.
    POST /tests/<test_id>/questions/<question_id>/attachment/ avec multipart (file).
    """
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


class MyTestSessionsView(APIView):
    """
    Liste des sessions de test du candidat connecté (déjà démarrées ou soumises).
    GET /api/v1/tests/my-sessions/ → candidat uniquement.
    """

    permission_classes = [IsCandidate]

    def get(self, request):
        if not getattr(request.user, 'is_candidate', False):
            return Response({'detail': 'Réservé aux candidats.'}, status=status.HTTP_403_FORBIDDEN)
        qs = (
            CandidateTestResult.objects.filter(application__candidate__user_id=request.user.id)
            .select_related('test', 'application__job_offer')
            .order_by('-created_at')
        )
        data = []
        for r in qs:
            job = r.application.job_offer
            data.append({
                'id': r.id,
                'application_id': r.application_id,
                'test_id': r.test_id,
                'test_title': r.test.title,
                'job_title': job.title if job else None,
                'status': r.status,
                'score': r.score,
                'max_score': r.max_score,
                'started_at': r.started_at,
                'submitted_at': r.submitted_at,
                'is_completed': r.is_completed,
            })
        return Response(data, status=status.HTTP_200_OK)


class MyAvailableTestsView(APIView):
    """
    Liste des tests disponibles pour le candidat (par candidature).
    Pour chaque candidature du candidat, retourne les tests actifs de l'entreprise de l'offre.
    GET /api/v1/tests/available-for-candidate/ → candidat uniquement.
    """

    permission_classes = [IsCandidate]

    def get(self, request):
        if not getattr(request.user, 'is_candidate', False):
            return Response({'detail': 'Réservé aux candidats.'}, status=status.HTTP_403_FORBIDDEN)
        apps = Application.objects.filter(
            candidate__user_id=request.user.id
        ).select_related('job_offer').prefetch_related('test_results')
        result = []
        for app in apps:
            company_id = app.job_offer.company_id if app.job_offer else None
            if not company_id:
                continue
            tests = list(
                Test.objects.filter(company_id=company_id, is_active=True)
                .values('id', 'title', 'duration_minutes', 'job_offer_id')
            )
            existing = {r.test_id: r for r in app.test_results.all()}
            for t in tests:
                # Si le test est lié à une offre précise, ne le proposer que pour cette offre
                job_offer_id = t.get('job_offer_id')
                if job_offer_id and job_offer_id != app.job_offer_id:
                    continue
                session = existing.get(t['id'])
                result.append({
                    'application_id': app.id,
                    'job_title': app.job_offer.title if app.job_offer else None,
                    'test_id': t['id'],
                    'test_title': t['title'],
                    'duration_minutes': t['duration_minutes'],
                    'session_id': session.id if session else None,
                    'status': session.status if session else 'pending',
                    'is_completed': session.is_completed if session else False,
                })
        return Response(result, status=status.HTTP_200_OK)


class CandidateTestResultListCreateView(generics.ListCreateAPIView):
    """
    Liste des résultats de tests (dashboard recruteur).
    """

    serializer_class = CandidateTestResultSerializer
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        qs = CandidateTestResult.objects.select_related('application', 'test', 'application__job_offer')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


class CandidateTestResultDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CandidateTestResultSerializer
    permission_classes = [IsRecruiterOrAdmin]

    def get_queryset(self):
        qs = CandidateTestResult.objects.select_related('application', 'test')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(application__job_offer__company_id=company_id)
        return qs


class CheckTestAccessView(APIView):
    """
    Vérifie l'accès d'un candidat à un test via email + code d'accès.

    Entrée: { email, code, test_id }
    - email doit correspondre à une Application shortlistée pour l'offre liée au test.
    - code doit correspondre à Test.access_code (actif).
    Retourne: { application_id, test_id } si accès autorisé.
    """

    permission_classes = [IsCandidate]

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        code = (request.data.get('code') or '').strip()
        test_id = request.data.get('test_id')
        if not email or not code or not test_id:
            return Response(
                {'detail': 'email, code et test_id sont requis.'},
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
                status=Application.Status.SHORTLISTED,
                candidate__email__iexact=email,
            )
            .select_related('candidate__user')
            .first()
        )
        if not app:
            return Response(
                {'detail': 'Aucune candidature shortlistée trouvée pour cet email et cette offre.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Optionnel: si le compte connecté est lié au candidat, on peut vérifier la cohérence
        if getattr(request.user, 'is_candidate', False) and app.candidate.user_id and app.candidate.user_id != request.user.id:
            return Response(
                {'detail': 'Cet email ne correspond pas à votre compte candidat.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response({'application_id': app.id, 'test_id': test.id}, status=status.HTTP_200_OK)


class SubmitTestAnswersView(generics.GenericAPIView):
    """
    Soumission des réponses : correction automatique QCM, calcul score, sauvegarde.

    Règles :
    - 1 seule tentative par candidature (enforcée par unique_together application/test).
    - Timer global basé sur started_at + duration_minutes.
    - Refus de la soumission si le temps est écoulé.
    """

    serializer_class = SubmitTestAnswersSerializer
    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        app = (
            Application.objects.filter(pk=ser.validated_data['application_id'])
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        test = Test.objects.filter(pk=ser.validated_data['test_id']).prefetch_related('questions').first()
        if not app or not test:
            return Response({'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        company_id = user.get_company_id()

        # Vérification multi-tenant pour recruteur/admin
        if company_id is not None and app.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        # Vérification côté candidat : doit être propriétaire de la candidature
        if getattr(user, 'is_candidate', False):
            if not app.candidate or app.candidate.user_id != user.id:
                return Response({'detail': 'Candidature non liée à ce compte candidat.'}, status=status.HTTP_403_FORBIDDEN)

        if test.company_id != app.job_offer.company_id:
            return Response(
                {'detail': "Le test ne correspond pas à l'entreprise de la candidature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupération / création du résultat pour vérifier le timer
        result, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        now = timezone.now()
        if not result.started_at:
            result.started_at = now
            result.status = CandidateTestResult.Status.IN_PROGRESS
            result.save(update_fields=['started_at', 'status', 'updated_at'])

        # Timer global : started_at + duration_minutes
        if test.duration_minutes:
            deadline = result.started_at + timedelta(minutes=test.duration_minutes)
            if now > deadline:
                result.status = CandidateTestResult.Status.EXPIRED
                result.is_completed = True
                result.submitted_at = result.submitted_at or now
                result.save(update_fields=['status', 'is_completed', 'submitted_at', 'updated_at'])
                return Response(
                    {'detail': 'Temps de test écoulé. Soumission refusée.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Soumission finale + scoring
        scored_result = submit_test_result(app, test, ser.validated_data['answers'])
        return Response(
            {
                'message': 'Résultats enregistrés.',
                'score': scored_result.score,
                'max_score': scored_result.max_score,
                'status': scored_result.status,
            },
            status=status.HTTP_200_OK,
        )


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
        ws.append(['Candidat', 'Email', 'Offre', 'Test', 'Score', 'Max', 'Soumis le'])
        for r in qs:
            ws.append([
                r.application.candidate.get_full_name(),
                r.application.candidate.email,
                r.application.job_offer.title,
                r.test.title,
                r.score,
                r.max_score,
                r.submitted_at.isoformat() if r.submitted_at else '',
            ])
        buffer = BytesIO()
        wb.save(buffer)
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="resultats_tests.xlsx"'
        return response


class StartTestSessionView(APIView):
    """
    Démarrage d'une session de test pour une candidature donnée.

    - Initialise started_at si absent.
    - Retourne le temps restant (en secondes) basé sur duration_minutes.
    - JWT obligatoire ; candidat limité à sa propre candidature, recruteur limité à sa company.
    """

    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        application_id = request.data.get('application_id')
        test_id = request.data.get('test_id')
        if not application_id or not test_id:
            return Response(
                {'detail': 'application_id et test_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        app = (
            Application.objects.filter(pk=application_id)
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        test = Test.objects.filter(pk=test_id).first()
        if not app or not test:
            return Response({'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        company_id = user.get_company_id()

        if company_id is not None and app.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        if getattr(user, 'is_candidate', False):
            if not app.candidate or app.candidate.user_id != user.id:
                return Response({'detail': 'Candidature non liée à ce compte candidat.'}, status=status.HTTP_403_FORBIDDEN)

        if test.company_id != app.job_offer.company_id:
            return Response(
                {'detail': "Le test ne correspond pas à l'entreprise de la candidature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        now = timezone.now()
        if not result.started_at:
            result.started_at = now
            result.status = CandidateTestResult.Status.IN_PROGRESS
            result.save(update_fields=['started_at', 'status', 'updated_at'])

        seconds_left = None
        if test.duration_minutes:
            deadline = result.started_at + timedelta(minutes=test.duration_minutes)
            remaining = (deadline - now).total_seconds()
            seconds_left = max(0, int(remaining))

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
    """
    Auto-save des réponses pendant le test (toutes les X secondes côté frontend).
    - Met à jour CandidateTestResult.answers.
    - Ne change pas le score ni le statut final.
    """

    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        application_id = request.data.get('application_id')
        test_id = request.data.get('test_id')
        answers = request.data.get('answers') or {}
        if not application_id or not test_id:
            return Response(
                {'detail': 'application_id et test_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        app = (
            Application.objects.filter(pk=application_id)
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        test = Test.objects.filter(pk=test_id).first()
        if not app or not test:
            return Response({'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        company_id = user.get_company_id()

        if company_id is not None and app.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        if getattr(user, 'is_candidate', False):
            if not app.candidate or app.candidate.user_id != user.id:
                return Response({'detail': 'Candidature non liée à ce compte candidat.'}, status=status.HTTP_403_FORBIDDEN)

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        # On ne recalcule pas le score ici, seulement la sauvegarde des réponses
        result.answers = answers
        if not result.started_at:
            result.started_at = timezone.now()
        if result.status == CandidateTestResult.Status.PENDING:
            result.status = CandidateTestResult.Status.IN_PROGRESS
        result.save(update_fields=['answers', 'started_at', 'status', 'updated_at'])
        return Response({'detail': 'Auto-save OK.'}, status=status.HTTP_200_OK)


class TabSwitchView(APIView):
    """
    Endpoint anti-triche basique : incrémente tab_switch_count pour un couple (application, test).
    Si le compteur dépasse 3, is_flagged = True.
    """

    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        application_id = request.data.get('application_id')
        test_id = request.data.get('test_id')
        if not application_id or not test_id:
            return Response(
                {'detail': 'application_id et test_id sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        app = (
            Application.objects.filter(pk=application_id)
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        test = Test.objects.filter(pk=test_id).first()
        if not app or not test:
            return Response({'detail': 'Candidature ou test introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        company_id = user.get_company_id()

        if company_id is not None and app.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        if getattr(user, 'is_candidate', False):
            if not app.candidate or app.candidate.user_id != user.id:
                return Response({'detail': 'Candidature non liée à ce compte candidat.'}, status=status.HTTP_403_FORBIDDEN)

        result, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )
        result.tab_switch_count += 1
        if result.tab_switch_count > 3:
            result.is_flagged = True
        result.save(update_fields=['tab_switch_count', 'is_flagged', 'updated_at'])
        return Response(
            {
                'tab_switch_count': result.tab_switch_count,
                'is_flagged': result.is_flagged,
            },
            status=status.HTTP_200_OK,
        )


class UploadAnswerFileView(APIView):
    """
    Upload d'un fichier réponse pour une question de type FILE_UPLOAD.
    - Enregistre le fichier dans Answer.file.
    - Ne déclenche pas de correction automatique (review manuelle).
    """

    permission_classes = [IsCandidate | IsRecruiterOrAdmin]

    def post(self, request):
        application_id = request.data.get('application_id')
        test_id = request.data.get('test_id')
        question_id = request.data.get('question_id')
        upload = request.FILES.get('file')

        if not application_id or not test_id or not question_id or not upload:
            return Response(
                {'detail': 'application_id, test_id, question_id et file sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        app = (
            Application.objects.filter(pk=application_id)
            .select_related('job_offer', 'candidate__user')
            .first()
        )
        test = Test.objects.filter(pk=test_id).first()
        question = Question.objects.filter(pk=question_id, test_id=test_id).first()

        if not app or not test or not question:
            return Response({'detail': 'Candidature, test ou question introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if question.question_type != Question.QuestionType.FILE_UPLOAD:
            return Response({'detail': 'Cette question n’accepte pas de fichier.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        company_id = user.get_company_id()

        if company_id is not None and app.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        if getattr(user, 'is_candidate', False):
            if not app.candidate or app.candidate.user_id != user.id:
                return Response({'detail': 'Candidature non liée à ce compte candidat.'}, status=status.HTTP_403_FORBIDDEN)

        from .models import CandidateTestResult, Answer  # import local pour éviter les cycles

        session, _ = CandidateTestResult.objects.get_or_create(
            application=app,
            test=test,
            defaults={'status': CandidateTestResult.Status.IN_PROGRESS},
        )

        answer, _ = Answer.objects.get_or_create(
            session=session,
            question=question,
        )
        answer.file = upload
        answer.save(update_fields=['file', 'updated_at'])

        return Response({'detail': 'Fichier réponse uploadé.'}, status=status.HTTP_200_OK)


class CandidateTestReportView(generics.RetrieveAPIView):
    """
    Rapport JSON détaillé pour un résultat de test (vue recruteur).

    Retourne :
    - score_total / max_score
    - score par section
    - score par compétence
    - détail par question (score, max, pending_manual_review, etc.)
    """

    permission_classes = [IsRecruiterOrAdmin]

    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        result = (
            CandidateTestResult.objects.select_related('test', 'application__job_offer')
            .filter(pk=pk)
            .first()
        )
        if not result:
            return Response({'detail': 'Résultat introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        company_id = request.user.get_company_id()
        if company_id is not None and result.application.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        report = build_test_report(result.test, result.answers or {})
        # Ajout de quelques métadonnées candidats / test
        payload = {
            'id': result.id,
            'application_id': result.application_id,
            'test_id': result.test_id,
            'status': result.status,
            'score': float(result.score or 0),
            'max_score': float(result.max_score or 0),
            'tab_switch_count': result.tab_switch_count,
            'is_flagged': result.is_flagged,
            'started_at': result.started_at,
            'submitted_at': result.submitted_at,
            'report': report,
        }
        return Response(payload, status=status.HTTP_200_OK)


class CandidateTestReportPDFView(APIView):
    """
    Génération d'un rapport PDF pour un résultat de test (vue recruteur).

    Le PDF contient :
    - informations candidat / offre / test
    - score global
    - scores par section
    - scores par compétence
    - indicateur de suspicion (flagged / tab switches)
    """

    permission_classes = [IsRecruiterOrAdmin]

    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        result = (
            CandidateTestResult.objects.select_related(
                'test',
                'application__candidate',
                'application__job_offer',
            )
            .filter(pk=pk)
            .first()
        )
        if not result:
            return Response({'detail': 'Résultat introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        company_id = request.user.get_company_id()
        if company_id is not None and result.application.job_offer.company_id != company_id:
            return Response({'detail': 'Non autorisé.'}, status=status.HTTP_403_FORBIDDEN)

        report = build_test_report(result.test, result.answers or {})

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
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

        # En-tête
        line('AfricaHire+ - Rapport de test candidat', font_size=14, bold=True)
        y -= 10

        # Infos candidat / offre / test
        line(f'Candidat : {candidate.get_full_name()} ({candidate.email})', font_size=11)
        line(f'Offre : {job.title}', font_size=11)
        line(f'Test : {result.test.title}', font_size=11)
        line(f'Statut : {result.status}', font_size=10)
        line(
            f'Score global : {report.get("score_total", 0)} / {report.get("max_score", 0)}',
            font_size=11,
            bold=True,
        )
        suspicion = 'FLAGGED' if result.is_flagged else 'Normal'
        line(
            f'Suspicion : {suspicion} (tab switches = {result.tab_switch_count})',
            font_size=10,
        )
        y -= 10

        # Sections
        sections = report.get('sections') or {}
        if sections:
            line('Score par section', font_size=12, bold=True)
            for _, sec in sections.items():
                line(f"- {sec.get('title')}: {sec.get('score')} / {sec.get('max_score')}", font_size=10)
            y -= 6

        # Compétences
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

