"""
Tests unitaires des services du module Tests : scoring, soumission, expiration, review.

Couvre tous les chemins critiques de `apps/tests/services.py` qui n'étaient
jamais testés. Toute régression sur la notation peut éliminer des candidats à
tort — chaque assertion ici verrouille un correctif spécifique.

Sections :
  - GradeQuestionTestCase            : `grade_question` (tous types)
  - GradeQuestionQCMMultiBugFixTestCase : FIX P2 du bug sur-cochage
  - NumericToleranceTestCase         : tolérance configurable par question
  - GradeTestAnswersTestCase         : pipeline complet + pending_review_points
  - SubmitTestResultTestCase         : persistance + audit log + bulk Answer
  - PassingScoreTestCase             : is_passed automatique
  - ExpireSessionTestCase            : expiration auto
  - ManualReviewAnswerTestCase       : review manuelle + audit log
  - QuestionOrderTestCase            : shuffle / pool stable par session
  - RecomputeTotalScoreTestCase      : auto-sync Test.total_score
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.applications.models import Application
from apps.candidates.models import Candidate
from apps.companies.models import Company
from apps.jobs.models import JobOffer
from apps.tests.models import (
    Answer,
    CandidateTestResult,
    Question,
    Test,
    TestAuditLog,
)
from apps.tests.services import (
    expire_session_if_needed,
    determine_question_order,
    grade_question,
    grade_test_answers,
    manual_review_answer,
    recompute_test_total_score,
    submit_test_result,
)


def _make_base_fixtures() -> tuple[Company, JobOffer, Candidate, Application, Test]:
    """Crée un ensemble cohérent Company → JobOffer → Candidate → Application → Test."""
    company = Company.objects.create(name='TC', slug=f'tc-{timezone.now().timestamp()}')
    job = JobOffer.objects.create(
        company=company, title='Dev', slug=f'dev-{timezone.now().timestamp()}',
        description='Job', status=JobOffer.Status.PUBLISHED,
    )
    candidate = Candidate.objects.create(
        company=company, email=f'c{timezone.now().timestamp()}@t.com',
        first_name='C', last_name='X',
    )
    app = Application.objects.create(
        job_offer=job, candidate=candidate,
        status=Application.Status.SHORTLISTED,
    )
    test = Test.objects.create(
        company=company, job_offer=job,
        title='Test 1', test_type=Test.TestType.TECHNICAL,
        duration_minutes=30,
    )
    return company, job, candidate, app, test


# ---------------------------------------------------------------------------
# grade_question — tous les types
# ---------------------------------------------------------------------------
class GradeQuestionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()

    def _make_q(self, **kw):
        defaults = dict(test=self.test, text='Q?', order=0, points=10)
        defaults.update(kw)
        return Question.objects.create(**defaults)

    # --- QCM single ---
    def test_qcm_single_correct(self):
        q = self._make_q(
            question_type=Question.QuestionType.QCM_SINGLE,
            options=[{'id': 'a', 'label': 'A', 'correct': True}, {'id': 'b', 'label': 'B'}],
        )
        pts, max_, meta = grade_question(q, 'a')
        self.assertEqual(pts, Decimal('10'))
        self.assertEqual(max_, Decimal('10'))
        self.assertTrue(meta['is_correct'])

    def test_qcm_single_wrong(self):
        q = self._make_q(
            question_type=Question.QuestionType.QCM_SINGLE,
            options=[{'id': 'a', 'label': 'A', 'correct': True}, {'id': 'b', 'label': 'B'}],
        )
        pts, _, meta = grade_question(q, 'b')
        self.assertEqual(pts, Decimal('0'))
        self.assertFalse(meta['is_correct'])

    def test_qcm_single_none_answer(self):
        q = self._make_q(
            question_type=Question.QuestionType.QCM_SINGLE,
            options=[{'id': 'a', 'correct': True}, {'id': 'b'}],
        )
        pts, _, meta = grade_question(q, None)
        self.assertEqual(pts, Decimal('0'))
        self.assertFalse(meta['is_correct'])

    def test_qcm_single_case_insensitive(self):
        q = self._make_q(
            question_type=Question.QuestionType.QCM_SINGLE,
            correct_answer='A',
            options=[{'id': 'A', 'label': 'A'}, {'id': 'B', 'label': 'B'}],
        )
        pts, _, _ = grade_question(q, 'a')
        self.assertEqual(pts, Decimal('10'))

    # --- Vrai / Faux ---
    def test_true_false_correct(self):
        q = self._make_q(question_type=Question.QuestionType.TRUE_FALSE, correct_answer=True)
        pts, _, _ = grade_question(q, 'true')
        self.assertEqual(pts, Decimal('10'))

        pts, _, _ = grade_question(q, 'oui')
        self.assertEqual(pts, Decimal('10'))

    def test_true_false_wrong(self):
        q = self._make_q(question_type=Question.QuestionType.TRUE_FALSE, correct_answer=True)
        pts, _, _ = grade_question(q, 'false')
        self.assertEqual(pts, Decimal('0'))

    # --- Open text / Code / File ---
    def test_open_text_pending_manual_review(self):
        q = self._make_q(question_type=Question.QuestionType.OPEN_TEXT)
        pts, max_, meta = grade_question(q, 'My answer is verbose.')
        self.assertEqual(pts, Decimal('0'))
        self.assertEqual(max_, Decimal('10'))
        self.assertTrue(meta['pending_manual_review'])
        self.assertIsNone(meta['is_correct'])

    def test_code_pending_manual_review(self):
        q = self._make_q(question_type=Question.QuestionType.CODE)
        _, _, meta = grade_question(q, 'def f(): return 1')
        self.assertTrue(meta['pending_manual_review'])

    def test_file_upload_pending_manual_review(self):
        q = self._make_q(question_type=Question.QuestionType.FILE_UPLOAD)
        _, _, meta = grade_question(q, 'uploaded.pdf')
        self.assertTrue(meta['pending_manual_review'])


# ---------------------------------------------------------------------------
# P2 — Fix bug QCM_MULTI sur-coché
# ---------------------------------------------------------------------------
class GradeQuestionQCMMultiBugFixTestCase(TestCase):
    """
    Verrouille le correctif P2 du bug critique : en v1, cocher TOUTES les
    réponses (y compris les mauvaises) donnait 100 %. En v2, on retire des
    points pour chaque mauvaise option cochée.
    """

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()

    def _qcm_multi(self, correct_ids: list[str]):
        return Question.objects.create(
            test=self.test, question_type=Question.QuestionType.QCM_MULTI,
            text='Cocher les bonnes réponses', order=0, points=10,
            correct_answer=correct_ids,
            options=[
                {'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'},
                {'id': 'c', 'label': 'C'}, {'id': 'd', 'label': 'D'},
                {'id': 'e', 'label': 'E'},
            ],
        )

    def test_perfect_answer_full_points(self):
        q = self._qcm_multi(['a', 'b'])
        pts, _, meta = grade_question(q, ['a', 'b'])
        self.assertEqual(pts, Decimal('10'))
        self.assertTrue(meta['is_correct'])

    def test_partial_correct_no_wrong_picks(self):
        """1 bonne sur 2 + 0 mauvaise = 5 / 10."""
        q = self._qcm_multi(['a', 'b'])
        pts, _, _ = grade_question(q, ['a'])
        self.assertEqual(pts, Decimal('5.00'))

    def test_all_options_picked_no_longer_perfect_score(self):
        """
        BUG CRITIQUE V1 : cocher TOUT donnait 100 %. En v2, on a 0 (3 mauvaises - 2 bonnes < 0).
        """
        q = self._qcm_multi(['a', 'b'])
        pts, _, meta = grade_question(q, ['a', 'b', 'c', 'd', 'e'])
        self.assertEqual(pts, Decimal('0'))
        self.assertFalse(meta['is_correct'])

    def test_one_correct_one_wrong_yields_zero(self):
        """good=1, wrong=1, total_correct=2 → (1-1)/2 = 0."""
        q = self._qcm_multi(['a', 'b'])
        pts, _, _ = grade_question(q, ['a', 'c'])
        self.assertEqual(pts, Decimal('0'))

    def test_two_correct_one_wrong_partial(self):
        """good=2, wrong=1, total_correct=2 → (2-1)/2 = 0.5 → 5 pts."""
        q = self._qcm_multi(['a', 'b'])
        pts, _, _ = grade_question(q, ['a', 'b', 'c'])
        self.assertEqual(pts, Decimal('5.00'))


# ---------------------------------------------------------------------------
# Numérique : tolérance configurable
# ---------------------------------------------------------------------------
class NumericToleranceTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()

    def _numeric(self, correct, tol=None):
        return Question.objects.create(
            test=self.test, question_type=Question.QuestionType.NUMERIC,
            text='Combien ?', order=0, points=10,
            correct_answer=correct, numeric_tolerance=tol,
        )

    def test_default_tolerance_1pct(self):
        q = self._numeric(100)
        pts, _, _ = grade_question(q, 100.5)  # dans ±1 %
        self.assertEqual(pts, Decimal('10'))
        pts, _, _ = grade_question(q, 102)  # hors ±1 %
        self.assertEqual(pts, Decimal('0'))

    def test_custom_tolerance_5pct(self):
        q = self._numeric(100, tol=0.05)
        pts, _, _ = grade_question(q, 104)  # dans ±5 %
        self.assertEqual(pts, Decimal('10'))
        pts, _, _ = grade_question(q, 106)
        self.assertEqual(pts, Decimal('0'))

    def test_strict_equality_when_tol_zero(self):
        q = self._numeric(42, tol=0.0)
        pts, _, _ = grade_question(q, 42)
        self.assertEqual(pts, Decimal('10'))
        pts, _, _ = grade_question(q, 42.001)
        self.assertEqual(pts, Decimal('0'))

    def test_invalid_user_input_returns_zero(self):
        q = self._numeric(10)
        pts, _, _ = grade_question(q, 'pas un nombre')
        self.assertEqual(pts, Decimal('0'))

    def test_correct_zero_requires_exact_or_tol_window(self):
        q = self._numeric(0, tol=0.0)
        pts, _, _ = grade_question(q, 0)
        self.assertEqual(pts, Decimal('10'))
        pts, _, _ = grade_question(q, 0.001)
        self.assertEqual(pts, Decimal('0'))


# ---------------------------------------------------------------------------
# grade_test_answers — pipeline complet
# ---------------------------------------------------------------------------
class GradeTestAnswersTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()
        cls.q1 = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.QCM_SINGLE,
            text='Q1', order=0, points=10,
            options=[{'id': 'a', 'correct': True}, {'id': 'b'}],
        )
        cls.q2 = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.OPEN_TEXT,
            text='Q2', order=1, points=20,
        )
        cls.q3 = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.NUMERIC,
            text='Q3', order=2, points=5,
            correct_answer=42,
        )

    def test_full_pipeline(self):
        answers = {self.q1.id: 'a', self.q2.id: 'long answer', self.q3.id: 42}
        total, max_, pending, details, agg = grade_test_answers(self.test, answers)
        self.assertEqual(total, Decimal('15'))     # 10 + 0 (open) + 5
        self.assertEqual(max_, Decimal('35'))      # 10 + 20 + 5
        self.assertEqual(pending, Decimal('20'))   # Q2 en attente review
        self.assertTrue(details[self.q2.id]['pending_manual_review'])
        self.assertIsNone(details[self.q2.id]['is_correct'])

    def test_lookup_answer_str_key(self):
        """answers peut utiliser des clés str (frontend JSON)."""
        answers = {str(self.q1.id): 'a'}
        total, _, _, _, _ = grade_test_answers(self.test, answers)
        self.assertEqual(total, Decimal('10'))

    def test_lookup_answer_legacy_question_prefix(self):
        """Compatibilité ascendante avec 'question_<id>'."""
        answers = {f'question_{self.q1.id}': 'a'}
        total, _, _, _, _ = grade_test_answers(self.test, answers)
        self.assertEqual(total, Decimal('10'))

    def test_missing_answer_yields_zero(self):
        total, _, _, _, _ = grade_test_answers(self.test, {})
        # Q1 + Q3 = 0 (réponses absentes), Q2 toujours 0 + pending
        self.assertEqual(total, Decimal('0'))


# ---------------------------------------------------------------------------
# submit_test_result + audit log + bulk Answer
# ---------------------------------------------------------------------------
class SubmitTestResultTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()
        cls.test.passing_score = Decimal('5.00')
        cls.test.save()
        cls.q1 = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.QCM_SINGLE,
            text='Q1', order=0, points=10,
            options=[{'id': 'a', 'correct': True}, {'id': 'b'}],
        )

    def test_creates_session_and_stores_score(self):
        result = submit_test_result(
            self.app, self.test, {self.q1.id: 'a'},
            client_ip='1.2.3.4',
        )
        self.assertEqual(result.status, CandidateTestResult.Status.SCORED)
        self.assertTrue(result.is_completed)
        self.assertEqual(result.score, Decimal('10'))
        self.assertEqual(result.max_score, Decimal('10'))
        self.assertTrue(result.is_passed)  # 10 >= 5
        self.assertEqual(result.client_ip, '1.2.3.4')

    def test_creates_answer_rows(self):
        result = submit_test_result(self.app, self.test, {self.q1.id: 'a'})
        rows = list(result.answer_rows.all())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].score_obtained, Decimal('10'))
        self.assertTrue(rows[0].is_correct)
        self.assertFalse(rows[0].pending_manual_review)

    def test_audit_log_on_status_change(self):
        submit_test_result(self.app, self.test, {self.q1.id: 'a'})
        log = TestAuditLog.objects.filter(action=TestAuditLog.Action.STATUS_CHANGE).first()
        self.assertIsNotNone(log)
        self.assertIn('automatique', log.reason.lower())

    def test_open_text_question_marks_pending(self):
        q_open = Question.objects.create(
            test=self.test, question_type=Question.QuestionType.OPEN_TEXT,
            text='Q2', order=1, points=20,
        )
        result = submit_test_result(self.app, self.test, {q_open.id: 'long answer'})
        self.assertEqual(result.pending_review_points, Decimal('20'))
        ans = result.answer_rows.get(question=q_open)
        self.assertTrue(ans.pending_manual_review)
        self.assertIsNone(ans.is_correct)

    def test_is_passed_false_when_below_threshold(self):
        self.test.passing_score = Decimal('15.00')
        self.test.save()
        result = submit_test_result(self.app, self.test, {self.q1.id: 'a'})
        self.assertFalse(result.is_passed)

    def test_is_passed_none_when_no_threshold(self):
        self.test.passing_score = None
        self.test.save()
        result = submit_test_result(self.app, self.test, {self.q1.id: 'a'})
        self.assertIsNone(result.is_passed)


# ---------------------------------------------------------------------------
# expire_session_if_needed — P4
# ---------------------------------------------------------------------------
class ExpireSessionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()
        cls.test.duration_minutes = 30
        cls.test.save()

    def test_not_expired_within_time(self):
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=10),
        )
        self.assertFalse(expire_session_if_needed(result))

    def test_expired_after_deadline(self):
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=31),
        )
        self.assertTrue(expire_session_if_needed(result))
        result.refresh_from_db()
        self.assertEqual(result.status, CandidateTestResult.Status.EXPIRED)
        self.assertTrue(result.is_completed)

    def test_no_duration_does_not_expire(self):
        self.test.duration_minutes = None
        self.test.save()
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.IN_PROGRESS,
            started_at=timezone.now() - timedelta(hours=24),
        )
        self.assertFalse(expire_session_if_needed(result))

    def test_already_finalized_no_op(self):
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.SCORED,
            is_completed=True,
            started_at=timezone.now() - timedelta(hours=2),
        )
        self.assertFalse(expire_session_if_needed(result))

    def test_creates_audit_log_on_expiration(self):
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.IN_PROGRESS,
            started_at=timezone.now() - timedelta(minutes=31),
        )
        expire_session_if_needed(result)
        log = TestAuditLog.objects.filter(session=result).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.new_value['status'], CandidateTestResult.Status.EXPIRED)


# ---------------------------------------------------------------------------
# manual_review_answer — P6 (audit + recalcul score session)
# ---------------------------------------------------------------------------
class ManualReviewAnswerTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()
        cls.test.passing_score = Decimal('15.00')
        cls.test.save()
        cls.q_open = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.OPEN_TEXT,
            text='Q1', order=0, points=20,
        )

    def setUp(self):
        # Soumission initiale → pending_review_points = 20, score = 0
        self.result = submit_test_result(self.app, self.test, {self.q_open.id: 'My answer'})
        self.answer = self.result.answer_rows.get(question=self.q_open)

    def test_review_updates_answer_score(self):
        manual_review_answer(
            self.answer, score_obtained=Decimal('15'), is_correct=True,
            reason='Bonne approche',
        )
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.score_obtained, Decimal('15'))
        self.assertTrue(self.answer.is_correct)
        self.assertFalse(self.answer.pending_manual_review)

    def test_review_recomputes_session_score(self):
        manual_review_answer(
            self.answer, score_obtained=Decimal('15'), is_correct=True,
        )
        self.result.refresh_from_db()
        self.assertEqual(self.result.score, Decimal('15'))
        self.assertEqual(self.result.pending_review_points, Decimal('0'))
        # passing_score = 15 → is_passed devient True après review
        self.assertTrue(self.result.is_passed)

    def test_review_audit_log(self):
        manual_review_answer(
            self.answer, score_obtained=Decimal('10'), is_correct=False,
            reason='Partiellement correct',
        )
        log = TestAuditLog.objects.filter(
            action=TestAuditLog.Action.MANUAL_REVIEW,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.new_value['score_obtained'], 10.0)
        self.assertEqual(log.reason, 'Partiellement correct')

    def test_review_score_clamped_to_max(self):
        """Si on essaie de mettre 100 alors que max=20, on plafonne à 20."""
        manual_review_answer(self.answer, score_obtained=100, is_correct=True)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.score_obtained, Decimal('20'))

    def test_review_negative_score_clamped_to_zero(self):
        manual_review_answer(self.answer, score_obtained=-5, is_correct=False)
        self.answer.refresh_from_db()
        self.assertEqual(self.answer.score_obtained, Decimal('0'))


# ---------------------------------------------------------------------------
# question_order — P5 shuffle / pool stable
# ---------------------------------------------------------------------------
class QuestionOrderTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()
        for i in range(5):
            Question.objects.create(
                test=cls.test, question_type=Question.QuestionType.QCM_SINGLE,
                text=f'Q{i}', order=i, points=1,
                options=[{'id': 'a', 'correct': True}, {'id': 'b'}],
            )

    def test_default_order_keeps_original(self):
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.PENDING,
        )
        order = determine_question_order(self.test, result)
        expected = list(self.test.questions.order_by('order', 'id').values_list('id', flat=True))
        self.assertEqual(order, expected)

    def test_shuffle_yields_stable_order_per_session(self):
        self.test.shuffle_questions = True
        self.test.save()
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.PENDING,
        )
        order1 = determine_question_order(self.test, result)
        order2 = determine_question_order(self.test, result)
        self.assertEqual(order1, order2)  # même session → même ordre

    def test_pool_subset(self):
        self.test.questions_per_session = 3
        self.test.save()
        result = CandidateTestResult.objects.create(
            application=self.app, test=self.test,
            status=CandidateTestResult.Status.PENDING,
        )
        order = determine_question_order(self.test, result)
        self.assertEqual(len(order), 3)
        # toutes les ids appartiennent au test
        valid_ids = set(self.test.questions.values_list('id', flat=True))
        self.assertTrue(set(order).issubset(valid_ids))


# ---------------------------------------------------------------------------
# recompute_test_total_score
# ---------------------------------------------------------------------------
class RecomputeTotalScoreTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.candidate, cls.app, cls.test = _make_base_fixtures()

    def test_sums_points(self):
        Question.objects.create(test=self.test, question_type='qcm_single', text='Q1', order=0, points=10)
        Question.objects.create(test=self.test, question_type='qcm_single', text='Q2', order=1, points=5)
        total = recompute_test_total_score(self.test)
        self.assertEqual(total, Decimal('15'))
        self.test.refresh_from_db()
        self.assertEqual(self.test.total_score, Decimal('15'))

    def test_empty_test_zero(self):
        total = recompute_test_total_score(self.test)
        self.assertEqual(total, Decimal('0'))
