"""
Tests du rôle Correcteur externe (P8).

Couvre les invariants critiques :
  - Anonymisation : aucun email/nom de candidat ne fuit dans les payloads.
  - Token : seul un correcteur avec un token valide accède aux endpoints
    correcteur. Pas de JWT ni de session. Token révoqué/expiré refusé.
  - Périmètre : un correcteur restreint à 2 candidats ne voit que ces 2-là.
  - Multi-tenant : un correcteur de company A ne peut pas accéder à un test
    de company B même avec un token (le token est unique à un test).
  - Override auto-correction : le correcteur peut modifier le score d'une
    réponse QCM déjà notée automatiquement. L'opération est tracée.
  - Recruteur : CRUD des assignations + révocation invalide le token.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

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
    Answer,
    CandidateTestResult,
    CorrectorAssignment,
    Question,
    Test,
    TestAuditLog,
)
from apps.tests.services import (
    assign_corrector,
    ensure_display_code,
    get_visible_sessions_for_corrector,
    manual_review_answer,
    submit_test_result,
)
from apps.users.models import User


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------
def _auth_client(user: User) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


def _build_world(num_candidates: int = 3):
    """Construit un test + N candidats ayant tous SCORED."""
    ts = timezone.now().timestamp()
    company = Company.objects.create(name='AcmeCorr', slug=f'acmecorr-{ts}')
    recruiter = User.objects.create_user(
        username=f'rec-{ts}',
        email=f'rec-{ts}@ex.com',
        password='pwd', role=User.Role.RECRUITER, company=company,
    )
    job = JobOffer.objects.create(
        company=company, title='Data Scientist',
        slug=f'ds-{timezone.now().timestamp()}',
        description='Job', status=JobOffer.Status.PUBLISHED,
    )
    test = Test.objects.create(
        company=company, job_offer=job,
        title='Test technique DS', test_type=Test.TestType.TECHNICAL,
        duration_minutes=60, passing_score=Decimal('50.00'),
    )
    # Une QCM auto-corrigée et une OPEN_TEXT
    q_qcm = Question.objects.create(
        test=test, question_type=Question.QuestionType.QCM_SINGLE,
        text='Quelle est la complexité de tri par insertion ?', order=0, points=10,
        correct_answer=['b'],
        options=[
            {'id': 'a', 'label': 'O(log n)'},
            {'id': 'b', 'label': 'O(n²)', 'correct': True},
            {'id': 'c', 'label': 'O(1)'},
        ],
    )
    q_open = Question.objects.create(
        test=test, question_type=Question.QuestionType.OPEN_TEXT,
        text='Expliquez l\'overfitting.', order=1, points=20,
    )

    candidates_data = []
    for i in range(num_candidates):
        cand_ts = timezone.now().timestamp()
        user = User.objects.create_user(
            username=f'cand{i}-{cand_ts}',
            email=f'cand{i}-{cand_ts}@ex.com',
            password='pwd', role=User.Role.CANDIDATE,
        )
        cand = Candidate.objects.create(
            company=company, user=user, email=user.email,
            first_name=f'Prenom{i}', last_name=f'Nom{i}',
        )
        app = Application.objects.create(
            job_offer=job, candidate=cand, status=Application.Status.SHORTLISTED,
        )
        # Le signal post_save lance compute_preselection() qui peut écraser
        # le status. On force la valeur SHORTLISTED après la création.
        Application.objects.filter(pk=app.pk).update(status=Application.Status.SHORTLISTED)
        app.refresh_from_db()
        # Soumission : QCM correct + open_text (pending)
        submit_test_result(
            app, test,
            {q_qcm.id: 'b', q_open.id: f'Réponse candidat {i}'},
        )
        candidates_data.append({'user': user, 'candidate': cand, 'application': app})

    return {
        'company': company, 'recruiter': recruiter, 'job': job, 'test': test,
        'q_qcm': q_qcm, 'q_open': q_open, 'candidates': candidates_data,
    }


def _corrector_client(token: str) -> APIClient:
    """Client API SANS JWT, uniquement avec le header X-Corrector-Token."""
    client = APIClient()
    client.credentials(HTTP_X_CORRECTOR_TOKEN=token)
    return client


# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------
class CorrectorAnonymizationTestCase(TestCase):

    def setUp(self):
        self.w = _build_world(num_candidates=2)
        self.assignment = assign_corrector(
            self.w['test'], email='corr@ext.com',
            assigned_by=self.w['recruiter'],
        )

    def test_session_list_does_not_leak_candidate_email_or_name(self):
        client = _corrector_client(self.assignment.token)
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.content.decode('utf-8')
        for c in self.w['candidates']:
            self.assertNotIn(c['candidate'].email, body)
            self.assertNotIn(c['candidate'].first_name, body)
            self.assertNotIn(c['candidate'].last_name, body)

    def test_session_list_returns_display_codes(self):
        client = _corrector_client(self.assignment.token)
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 200)
        sessions = resp.json()['sessions']
        self.assertEqual(len(sessions), 2)
        for s in sessions:
            self.assertTrue(s['display_code'].startswith('C-'))
            self.assertNotIn('email', s)
            self.assertNotIn('candidate', s)
            self.assertNotIn('first_name', s)

    def test_session_detail_does_not_leak_candidate_info(self):
        result = CandidateTestResult.objects.filter(test=self.w['test']).first()
        client = _corrector_client(self.assignment.token)
        resp = client.get(f'/api/v1/tests/correctors/sessions/{result.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.content.decode('utf-8')
        for c in self.w['candidates']:
            self.assertNotIn(c['candidate'].email, body)
            self.assertNotIn(c['candidate'].first_name, body)
            self.assertNotIn(c['candidate'].last_name, body)

    def test_display_code_is_stable_per_session(self):
        result = CandidateTestResult.objects.filter(test=self.w['test']).first()
        code1 = ensure_display_code(result)
        code2 = ensure_display_code(result)
        self.assertEqual(code1, code2)
        self.assertTrue(code1.startswith('C-'))


# ---------------------------------------------------------------------------
# Token : sécurité d'accès
# ---------------------------------------------------------------------------
class CorrectorTokenSecurityTestCase(TestCase):

    def setUp(self):
        self.w = _build_world(num_candidates=1)
        self.assignment = assign_corrector(
            self.w['test'], email='corr@ext.com',
            assigned_by=self.w['recruiter'],
        )

    def test_missing_token_rejected(self):
        client = APIClient()
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_invalid_token_rejected(self):
        client = _corrector_client('not-a-real-token-12345')
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_revoked_token_rejected(self):
        self.assignment.is_revoked = True
        self.assignment.revoked_at = timezone.now()
        self.assignment.save()
        client = _corrector_client(self.assignment.token)
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_expired_token_rejected(self):
        self.assignment.expires_at = timezone.now() - timedelta(hours=1)
        self.assignment.save()
        client = _corrector_client(self.assignment.token)
        resp = client.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_token_in_query_string_works(self):
        client = APIClient()
        resp = client.get(
            f'/api/v1/tests/correctors/sessions/?token={self.assignment.token}'
        )
        self.assertEqual(resp.status_code, 200)

    def test_use_count_increments_on_each_call(self):
        client = _corrector_client(self.assignment.token)
        self.assertEqual(self.assignment.use_count, 0)
        client.get('/api/v1/tests/correctors/sessions/')
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.use_count, 1)
        self.assertIsNotNone(self.assignment.first_used_at)
        client.get('/api/v1/tests/correctors/sessions/')
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.use_count, 2)


# ---------------------------------------------------------------------------
# Périmètre : restriction à certains candidats
# ---------------------------------------------------------------------------
class CorrectorScopeRestrictionTestCase(TestCase):

    def setUp(self):
        self.w = _build_world(num_candidates=4)

    def test_all_candidates_scope_sees_everyone(self):
        a = assign_corrector(
            self.w['test'], email='c@ext.com',
            assigned_by=self.w['recruiter'],
        )
        sessions = list(get_visible_sessions_for_corrector(a))
        self.assertEqual(len(sessions), 4)

    def test_restricted_scope_sees_only_assigned(self):
        # Seuls les candidats 0 et 2 sont attribués
        assigned_ids = [
            self.w['candidates'][0]['application'].id,
            self.w['candidates'][2]['application'].id,
        ]
        a = assign_corrector(
            self.w['test'], email='c@ext.com',
            assigned_by=self.w['recruiter'],
            assigned_application_ids=assigned_ids,
        )
        sessions = list(get_visible_sessions_for_corrector(a))
        self.assertEqual(len(sessions), 2)
        app_ids = {s.application_id for s in sessions}
        self.assertEqual(app_ids, set(assigned_ids))

    def test_restricted_scope_blocks_detail_of_unassigned(self):
        assigned_ids = [self.w['candidates'][0]['application'].id]
        a = assign_corrector(
            self.w['test'], email='c@ext.com',
            assigned_by=self.w['recruiter'],
            assigned_application_ids=assigned_ids,
        )
        # Tente d'accéder à un candidat NON attribué
        other_result = CandidateTestResult.objects.filter(
            application=self.w['candidates'][1]['application'],
        ).first()
        client = _corrector_client(a.token)
        resp = client.get(f'/api/v1/tests/correctors/sessions/{other_result.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_restricted_scope_blocks_review_of_unassigned(self):
        assigned_ids = [self.w['candidates'][0]['application'].id]
        a = assign_corrector(
            self.w['test'], email='c@ext.com',
            assigned_by=self.w['recruiter'],
            assigned_application_ids=assigned_ids,
        )
        other_result = CandidateTestResult.objects.filter(
            application=self.w['candidates'][1]['application'],
        ).first()
        other_answer = other_result.answer_rows.first()
        client = _corrector_client(a.token)
        resp = client.post(
            f'/api/v1/tests/correctors/answers/{other_answer.id}/review/',
            {'score': '5.00'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Override de l'auto-correction (QCM, true_false, numérique)
# ---------------------------------------------------------------------------
class CorrectorCanOverrideAutoGradedTestCase(TestCase):

    def setUp(self):
        self.w = _build_world(num_candidates=1)
        self.assignment = assign_corrector(
            self.w['test'], email='c@ext.com',
            assigned_by=self.w['recruiter'],
        )
        self.session = CandidateTestResult.objects.get(test=self.w['test'])
        # La QCM a été notée 10/10 par l'auto-corrigé
        self.qcm_answer = self.session.answer_rows.get(question=self.w['q_qcm'])
        self.assertEqual(self.qcm_answer.score_obtained, Decimal('10'))
        self.assertTrue(self.qcm_answer.is_correct)
        self.assertFalse(self.qcm_answer.pending_manual_review)

    def test_corrector_can_lower_auto_graded_qcm(self):
        client = _corrector_client(self.assignment.token)
        resp = client.post(
            f'/api/v1/tests/correctors/answers/{self.qcm_answer.id}/review/',
            {'score': '5.00', 'is_correct': False, 'reason': 'Énoncé ambigu'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.qcm_answer.refresh_from_db()
        self.assertEqual(self.qcm_answer.score_obtained, Decimal('5'))
        self.assertFalse(self.qcm_answer.is_correct)

    def test_corrector_can_increase_auto_graded_qcm(self):
        # Simulate that auto-grade gave 0
        self.qcm_answer.score_obtained = Decimal('0')
        self.qcm_answer.is_correct = False
        self.qcm_answer.save()
        client = _corrector_client(self.assignment.token)
        resp = client.post(
            f'/api/v1/tests/correctors/answers/{self.qcm_answer.id}/review/',
            {'score': '10.00', 'is_correct': True, 'reason': 'Réponse équivalente'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.qcm_answer.refresh_from_db()
        self.assertEqual(self.qcm_answer.score_obtained, Decimal('10'))
        self.assertTrue(self.qcm_answer.is_correct)

    def test_corrector_review_clamped_to_max_points(self):
        client = _corrector_client(self.assignment.token)
        resp = client.post(
            f'/api/v1/tests/correctors/answers/{self.qcm_answer.id}/review/',
            {'score': '999.00', 'is_correct': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.qcm_answer.refresh_from_db()
        self.assertEqual(self.qcm_answer.score_obtained, Decimal('10'))  # plafonné à 10

    def test_corrector_review_creates_audit_log_with_corrector_fk(self):
        client = _corrector_client(self.assignment.token)
        client.post(
            f'/api/v1/tests/correctors/answers/{self.qcm_answer.id}/review/',
            {'score': '5.00', 'is_correct': False, 'reason': 'test'},
            format='json',
        )
        log = TestAuditLog.objects.filter(
            action=TestAuditLog.Action.CORRECTOR_REVIEW,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.corrector_id, self.assignment.id)
        self.assertIsNone(log.actor)
        self.assertEqual(log.reason, 'test')

    def test_corrector_review_recomputes_session_score(self):
        # La session a 10 (QCM) + 0 (open) = 10. On baisse QCM à 5 → score = 5
        client = _corrector_client(self.assignment.token)
        client.post(
            f'/api/v1/tests/correctors/answers/{self.qcm_answer.id}/review/',
            {'score': '5.00', 'is_correct': False},
            format='json',
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.score, Decimal('5'))


# ---------------------------------------------------------------------------
# Recruteur : CRUD assignations
# ---------------------------------------------------------------------------
class RecruiterAssignmentCRUDTestCase(TestCase):

    def setUp(self):
        self.w = _build_world(num_candidates=2)
        self.url = f'/api/v1/tests/{self.w["test"].id}/correctors/'

    def test_create_corrector_assignment(self):
        client = _auth_client(self.w['recruiter'])
        resp = client.post(self.url, {
            'email': 'corr@ext.com',
            'full_name': 'Jean Correcteur',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(CorrectorAssignment.objects.filter(email='corr@ext.com').exists())

    def test_create_with_specific_candidates_restricts_scope(self):
        client = _auth_client(self.w['recruiter'])
        app_ids = [self.w['candidates'][0]['application'].id]
        resp = client.post(self.url, {
            'email': 'corr@ext.com',
            'assigned_application_ids': app_ids,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        a = CorrectorAssignment.objects.get(email='corr@ext.com')
        self.assertFalse(a.all_candidates)
        self.assertEqual(set(a.assigned_applications.values_list('id', flat=True)), set(app_ids))

    def test_create_without_application_ids_means_all(self):
        client = _auth_client(self.w['recruiter'])
        resp = client.post(self.url, {'email': 'corr@ext.com'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        a = CorrectorAssignment.objects.get(email='corr@ext.com')
        self.assertTrue(a.all_candidates)

    def test_list_assignments_returns_only_test_correctors(self):
        # En crée 2 sur ce test
        assign_corrector(self.w['test'], 'a@ext.com', assigned_by=self.w['recruiter'])
        assign_corrector(self.w['test'], 'b@ext.com', assigned_by=self.w['recruiter'])
        client = _auth_client(self.w['recruiter'])
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        emails = {a['email'] for a in data}
        self.assertEqual(emails, {'a@ext.com', 'b@ext.com'})

    def test_list_does_not_expose_full_token(self):
        a = assign_corrector(self.w['test'], 'a@ext.com', assigned_by=self.w['recruiter'])
        client = _auth_client(self.w['recruiter'])
        resp = client.get(self.url)
        body = resp.content.decode('utf-8')
        self.assertNotIn(a.token, body)

    def test_revoke_invalidates_token(self):
        a = assign_corrector(self.w['test'], 'r@ext.com', assigned_by=self.w['recruiter'])
        token = a.token
        client = _auth_client(self.w['recruiter'])
        resp = client.delete(f'/api/v1/tests/correctors/{a.id}/')
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertTrue(a.is_revoked)
        # Le token n'est plus utilisable
        c2 = _corrector_client(token)
        resp = c2.get('/api/v1/tests/correctors/sessions/')
        self.assertEqual(resp.status_code, 403)

    def test_reassigning_same_email_rotates_token(self):
        a1 = assign_corrector(self.w['test'], 'same@ext.com', assigned_by=self.w['recruiter'])
        old_token = a1.token
        # Re-create via API
        client = _auth_client(self.w['recruiter'])
        resp = client.post(self.url, {'email': 'same@ext.com'}, format='json')
        self.assertEqual(resp.status_code, 201)
        a1.refresh_from_db()
        self.assertNotEqual(a1.token, old_token)

    def test_multi_tenant_isolation(self):
        # Recruteur d'une autre company ne peut pas voir les correcteurs de ce test
        ts = timezone.now().timestamp()
        other_company = Company.objects.create(name='Other', slug=f'other-{ts}')
        other_rec = User.objects.create_user(
            username=f'other-{ts}',
            email=f'other-{ts}@ex.com',
            password='pwd', role=User.Role.RECRUITER, company=other_company,
        )
        assign_corrector(self.w['test'], 'a@ext.com', assigned_by=self.w['recruiter'])
        client = _auth_client(other_rec)
        resp = client.get(self.url)
        # 403 (test n'appartient pas à cette company)
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Auth check endpoint
# ---------------------------------------------------------------------------
class CorrectorAuthCheckTestCase(TestCase):

    def test_check_returns_test_info_and_scope(self):
        w = _build_world(num_candidates=2)
        a = assign_corrector(w['test'], 'c@ext.com', assigned_by=w['recruiter'])
        client = _corrector_client(a.token)
        resp = client.post('/api/v1/tests/correctors/auth/check/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['test']['title'], w['test'].title)
        self.assertEqual(data['test']['job_role'], 'Data Scientist')
        self.assertEqual(data['corrector']['scope'], 'all_candidates')
        self.assertEqual(data['sessions_to_review'], 2)

    def test_check_restricted_scope_reports_correctly(self):
        w = _build_world(num_candidates=3)
        a = assign_corrector(
            w['test'], 'c@ext.com', assigned_by=w['recruiter'],
            assigned_application_ids=[w['candidates'][0]['application'].id],
        )
        client = _corrector_client(a.token)
        resp = client.post('/api/v1/tests/correctors/auth/check/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['corrector']['scope'], 'restricted')
        self.assertEqual(data['corrector']['assigned_count'], 1)
        self.assertEqual(data['sessions_to_review'], 1)
