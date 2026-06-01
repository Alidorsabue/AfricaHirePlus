"""
Tests d'intégration des views API du module Tests.

Couvre les chemins critiques :
  - Sécurité (P1) : un candidat ne peut PAS accéder à /tests/<id>/ (correct_answer).
  - Sécurité (P1) : un candidat ne peut accéder à /tests/<id>/take/ que s'il
    est shortlisté+ sur l'offre du test.
  - Sécurité (P1) : verrou anti-modification après soumission.
  - Sécurité (P1) : upload de fichier — extensions/MIME interdits.
  - Workflow (P4) : timer expiré → 400.
  - Anti-triche (P5) : token unique par candidat (check-access).
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.applications.models import Application
from apps.candidates.models import Candidate
from apps.companies.models import Company
from apps.jobs.models import JobOffer
from apps.tests.models import (
    CandidateTestResult,
    Question,
    Test,
    TestAccessGrant,
)
from apps.users.models import User


def _auth_client(user: User) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


def _make_world(app_status=Application.Status.SHORTLISTED):
    """Construit Company + JobOffer + Test + Candidat + Application + Users."""
    company = Company.objects.create(name='AcmeCo', slug=f'acme-{timezone.now().timestamp()}')
    job = JobOffer.objects.create(
        company=company, title='Dev', slug=f'dev-{timezone.now().timestamp()}',
        description='Job', status=JobOffer.Status.PUBLISHED,
    )
    test = Test.objects.create(
        company=company, job_offer=job,
        title='Test technique', test_type=Test.TestType.TECHNICAL,
        duration_minutes=30, passing_score=50,
        access_code='SECRET123', is_active=True,
    )
    Question.objects.create(
        test=test, question_type=Question.QuestionType.QCM_SINGLE,
        text='Q1', order=0, points=10, correct_answer=['a'],
        options=[{'id': 'a', 'label': 'A', 'correct': True}, {'id': 'b', 'label': 'B'}],
    )
    Question.objects.create(
        test=test, question_type=Question.QuestionType.OPEN_TEXT,
        text='Expliquez', order=1, points=20,
    )
    ts = timezone.now().timestamp()
    candidate_user = User.objects.create_user(
        username=f'cand-{ts}',
        email=f'cand-{ts}@ex.com',
        password='pwd12345', role=User.Role.CANDIDATE,
    )
    candidate = Candidate.objects.create(
        company=company, user=candidate_user, email=candidate_user.email,
        first_name='C', last_name='X',
    )
    application = Application.objects.create(
        job_offer=job, candidate=candidate, status=app_status,
    )
    # Le signal post_save lance compute_preselection() qui peut écraser le status.
    # On force la valeur attendue par le test après la création.
    Application.objects.filter(pk=application.pk).update(status=app_status)
    application.refresh_from_db()
    recruiter_user = User.objects.create_user(
        username=f'rec-{ts}',
        email=f'rec-{ts}@ex.com',
        password='pwd12345', role=User.Role.RECRUITER, company=company,
    )
    return {
        'company': company, 'job': job, 'test': test,
        'candidate': candidate, 'application': application,
        'candidate_user': candidate_user, 'recruiter_user': recruiter_user,
    }


# ---------------------------------------------------------------------------
# P1 — Sécurité : un candidat ne peut PAS voir le test via /tests/<id>/
# ---------------------------------------------------------------------------
class CandidateAccessToTestDetailTestCase(TestCase):

    def setUp(self):
        self.w = _make_world()

    def test_candidate_cannot_access_test_detail_endpoint(self):
        """Le candidat n'a aucun droit sur /tests/<id>/ (qui exposerait correct_answer)."""
        client = _auth_client(self.w['candidate_user'])
        resp = client.get(f'/api/v1/tests/{self.w["test"].id}/')
        # Soit 403 (permission), soit 404 (queryset filtré → none)
        self.assertIn(resp.status_code, (403, 404))

    def test_candidate_take_endpoint_returns_questions_without_correct_answer(self):
        client = _auth_client(self.w['candidate_user'])
        resp = client.get(
            f'/api/v1/tests/{self.w["test"].id}/take/'
            f'?application_id={self.w["application"].id}'
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        for q in resp.json()['questions']:
            self.assertNotIn('correct_answer', q)
            for opt in q.get('options', []):
                self.assertNotIn('correct', opt)


# ---------------------------------------------------------------------------
# P1 — Sécurité : statut Application requis pour passer un test
# ---------------------------------------------------------------------------
class CandidateMustBeShortlistedTestCase(TestCase):

    def test_applied_candidate_cannot_start_session(self):
        w = _make_world(app_status=Application.Status.APPLIED)
        client = _auth_client(w['candidate_user'])
        resp = client.post('/api/v1/tests/start-session/', {
            'application_id': w['application'].id,
            'test_id': w['test'].id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_rejected_candidate_cannot_take_test(self):
        w = _make_world(app_status=Application.Status.REJECTED)
        client = _auth_client(w['candidate_user'])
        resp = client.get(
            f'/api/v1/tests/{w["test"].id}/take/?application_id={w["application"].id}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_shortlisted_candidate_can_start_session(self):
        w = _make_world(app_status=Application.Status.SHORTLISTED)
        client = _auth_client(w['candidate_user'])
        resp = client.post('/api/v1/tests/start-session/', {
            'application_id': w['application'].id,
            'test_id': w['test'].id,
        }, format='json')
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# P1 — Verrou anti-modification post-soumission
# ---------------------------------------------------------------------------
class PostSubmissionLockTestCase(TestCase):

    def setUp(self):
        self.w = _make_world()
        # Crée une session déjà SCORED
        self.result = CandidateTestResult.objects.create(
            application=self.w['application'], test=self.w['test'],
            status=CandidateTestResult.Status.SCORED, is_completed=True,
            started_at=timezone.now() - timedelta(minutes=10),
            submitted_at=timezone.now(),
            score=10, max_score=30,
        )

    def test_autosave_blocked_after_submit(self):
        client = _auth_client(self.w['candidate_user'])
        resp = client.post('/api/v1/tests/auto-save/', {
            'application_id': self.w['application'].id,
            'test_id': self.w['test'].id,
            'answers': {'1': 'modified'},
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.result.refresh_from_db()
        # Les réponses ne doivent pas avoir été écrasées
        self.assertNotIn('modified', str(self.result.answers))

    def test_submit_again_blocked(self):
        client = _auth_client(self.w['candidate_user'])
        resp = client.post('/api/v1/tests/submit-answers/', {
            'application_id': self.w['application'].id,
            'test_id': self.w['test'].id,
            'answers': {'1': 'a'},
        }, format='json')
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# P1 — Sécurité upload : extensions interdites
# ---------------------------------------------------------------------------
class UploadFileSecurityTestCase(TestCase):

    def setUp(self):
        self.w = _make_world()
        self.file_q = Question.objects.create(
            test=self.w['test'], question_type=Question.QuestionType.FILE_UPLOAD,
            text='Uploadez', order=2, points=10,
        )

    def _post_file(self, filename: str, content: bytes = b'data', content_type: str | None = None):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client = _auth_client(self.w['candidate_user'])
        upload = SimpleUploadedFile(filename, content, content_type=content_type)
        return client.post(
            '/api/v1/tests/upload-file/',
            {
                'application_id': self.w['application'].id,
                'test_id': self.w['test'].id,
                'question_id': self.file_q.id,
                'file': upload,
            },
            format='multipart',
        )

    def test_exe_extension_rejected(self):
        resp = self._post_file('payload.exe', b'MZ\x90' * 100, content_type='application/octet-stream')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Extension', resp.json()['detail'])

    def test_bat_extension_rejected(self):
        resp = self._post_file('cmd.bat', b'echo hi', content_type='text/plain')
        self.assertEqual(resp.status_code, 400)

    def test_sh_extension_rejected(self):
        resp = self._post_file('install.sh', b'#!/bin/sh\nrm -rf /', content_type='text/plain')
        self.assertEqual(resp.status_code, 400)

    def test_pdf_accepted(self):
        resp = self._post_file('cv.pdf', b'%PDF-1.4\n%EOF', content_type='application/pdf')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_oversized_file_rejected(self):
        big = b'x' * (26 * 1024 * 1024)
        resp = self._post_file('big.pdf', big, content_type='application/pdf')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('trop volumineux', resp.json()['detail'])


# ---------------------------------------------------------------------------
# P4 — Workflow : timer expiré
# ---------------------------------------------------------------------------
class TimerExpirationTestCase(TestCase):

    def test_submit_after_deadline_rejected(self):
        w = _make_world()
        # Créer une session démarrée il y a longtemps
        CandidateTestResult.objects.create(
            application=w['application'], test=w['test'],
            status=CandidateTestResult.Status.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=45),  # > 30 min duration
        )
        client = _auth_client(w['candidate_user'])
        resp = client.post('/api/v1/tests/submit-answers/', {
            'application_id': w['application'].id,
            'test_id': w['test'].id,
            'answers': {},
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('écoulé', resp.json()['detail'].lower())


# ---------------------------------------------------------------------------
# P5 — Token d'accès unique par candidat
# ---------------------------------------------------------------------------
class TestAccessGrantTokenTestCase(TestCase):

    def setUp(self):
        self.w = _make_world()
        self.grant = TestAccessGrant.objects.create(
            test=self.w['test'], application=self.w['application'],
        )

    def test_check_access_with_token(self):
        client = _auth_client(self.w['candidate_user'])
        resp = client.post('/api/v1/tests/check-access/', {
            'token': self.grant.token,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['test_id'], self.w['test'].id)
        self.assertEqual(resp.json()['application_id'], self.w['application'].id)

    def test_revoked_token_rejected(self):
        self.grant.is_revoked = True
        self.grant.revoked_at = timezone.now()
        self.grant.save()
        client = _auth_client(self.w['candidate_user'])
        resp = client.post('/api/v1/tests/check-access/', {
            'token': self.grant.token,
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_expired_token_rejected(self):
        self.grant.expires_at = timezone.now() - timedelta(hours=1)
        self.grant.save()
        client = _auth_client(self.w['candidate_user'])
        resp = client.post('/api/v1/tests/check-access/', {
            'token': self.grant.token,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_token_marks_used_at(self):
        self.assertIsNone(self.grant.used_at)
        client = _auth_client(self.w['candidate_user'])
        client.post('/api/v1/tests/check-access/', {
            'token': self.grant.token,
        }, format='json')
        self.grant.refresh_from_db()
        self.assertIsNotNone(self.grant.used_at)


# ---------------------------------------------------------------------------
# Multi-tenant : un candidat ne voit jamais les tests d'une autre company
# ---------------------------------------------------------------------------
class MultiTenantIsolationTestCase(TestCase):

    def test_candidate_cannot_take_test_of_another_company(self):
        w1 = _make_world()
        w2 = _make_world()
        client = _auth_client(w1['candidate_user'])  # user de la company1
        # Tente d'accéder au test de company2 avec son application1
        resp = client.get(
            f'/api/v1/tests/{w2["test"].id}/take/?application_id={w1["application"].id}'
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('entreprise', resp.json()['detail'].lower())


# ---------------------------------------------------------------------------
# IP tracking — P1.6
# ---------------------------------------------------------------------------
class ClientIPRecordingTestCase(TestCase):

    def test_start_session_records_client_ip(self):
        w = _make_world()
        client = _auth_client(w['candidate_user'])
        resp = client.post(
            '/api/v1/tests/start-session/',
            {'application_id': w['application'].id, 'test_id': w['test'].id},
            format='json',
            REMOTE_ADDR='198.51.100.42',
        )
        self.assertEqual(resp.status_code, 200)
        result = CandidateTestResult.objects.get(
            application=w['application'], test=w['test'],
        )
        self.assertEqual(result.client_ip, '198.51.100.42')
        self.assertEqual(result.last_seen_ip, '198.51.100.42')
