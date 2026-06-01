"""
Tests unitaires des serializers du module Tests.

Verrouille deux fronts critiques :

  P1 — Sécurité : aucune bonne réponse ne doit JAMAIS être sérialisée pour un
  candidat. On vérifie pour chaque type de question et chaque format d'options.

  P3 — Validation : on ne doit jamais pouvoir créer une question incohérente
  (QCM sans options, numérique sans correct_answer, points=0, etc.).
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Company
from apps.jobs.models import JobOffer
from apps.tests.models import Question, Section, Test
from apps.tests.serializers import (
    CandidateQuestionSerializer,
    CandidateTestSerializer,
    QuestionSerializer,
    QuestionWriteSerializer,
    TestWriteSerializer,
    _strip_correct_flag_from_options,
)


def _make_test():
    company = Company.objects.create(name='SC', slug=f'sc-{timezone.now().timestamp()}')
    job = JobOffer.objects.create(
        company=company, title='Dev', slug=f'dev-{timezone.now().timestamp()}',
        description='Job', status=JobOffer.Status.PUBLISHED,
    )
    return company, job, Test.objects.create(
        company=company, job_offer=job, title='Test', test_type=Test.TestType.TECHNICAL,
    )


# ---------------------------------------------------------------------------
# P1 — Sécurité : aucune fuite vers le candidat
# ---------------------------------------------------------------------------
class CandidateSerializerSecurityTestCase(TestCase):
    """Le serializer candidat ne DOIT JAMAIS exposer correct_answer ni correct=true."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.test = _make_test()
        cls.q_qcm = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.QCM_SINGLE,
            text='Quelle est la capitale ?', order=0, points=10,
            correct_answer=['paris'],
            options=[
                {'id': 'paris', 'label': 'Paris', 'correct': True},
                {'id': 'lyon', 'label': 'Lyon', 'correct': False},
            ],
            competencies=['geo'],
        )
        cls.q_open = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.OPEN_TEXT,
            text='Expliquez X', order=1, points=20,
            correct_answer='Réponse modèle confidentielle',
        )
        cls.q_numeric = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.NUMERIC,
            text='2+2 ?', order=2, points=5, correct_answer=4,
        )

    def test_qcm_does_not_expose_correct_answer(self):
        data = CandidateQuestionSerializer(self.q_qcm).data
        self.assertNotIn('correct_answer', data)

    def test_qcm_options_strip_correct_flag(self):
        data = CandidateQuestionSerializer(self.q_qcm).data
        for opt in data['options']:
            self.assertNotIn('correct', opt)
            self.assertIn('id', opt)
            self.assertIn('label', opt)

    def test_open_text_does_not_expose_correct_answer(self):
        data = CandidateQuestionSerializer(self.q_open).data
        self.assertNotIn('correct_answer', data)
        self.assertNotIn('Réponse modèle confidentielle', str(data))

    def test_numeric_does_not_expose_correct_answer(self):
        data = CandidateQuestionSerializer(self.q_numeric).data
        self.assertNotIn('correct_answer', data)

    def test_test_serializer_questions_safe(self):
        """Le serializer Test pour candidat applique le filtrage à toutes ses questions."""
        data = CandidateTestSerializer(self.test).data
        for q in data['questions']:
            self.assertNotIn('correct_answer', q)
            for opt in q.get('options', []):
                self.assertNotIn('correct', opt)

    def test_test_serializer_excludes_access_code(self):
        """access_code est confidentiel — un candidat ne doit pas le voir."""
        data = CandidateTestSerializer(self.test).data
        self.assertNotIn('access_code', data)

    def test_strip_helper_handles_malformed_input(self):
        """Robustesse du helper face à des options malformées."""
        self.assertEqual(_strip_correct_flag_from_options(None), [])
        self.assertEqual(_strip_correct_flag_from_options('not a list'), [])
        self.assertEqual(_strip_correct_flag_from_options([None, 'string']), [])
        # Une option avec une clé exotique 'is_correct' n'est PAS dans la whitelist → filtrée
        result = _strip_correct_flag_from_options([{'id': 'a', 'is_correct': True}])
        self.assertEqual(result, [{'id': 'a'}])


# ---------------------------------------------------------------------------
# P1 — Le serializer RECRUTEUR continue d'exposer (c'est attendu)
# ---------------------------------------------------------------------------
class RecruiterSerializerExposesCorrectAnswerTestCase(TestCase):
    """Le serializer recruteur DOIT exposer correct_answer (sinon il ne peut pas éditer)."""

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, cls.test = _make_test()
        cls.q = Question.objects.create(
            test=cls.test, question_type=Question.QuestionType.QCM_SINGLE,
            text='Q', order=0, points=10,
            correct_answer=['a'],
            options=[{'id': 'a', 'label': 'A', 'correct': True}],
        )

    def test_correct_answer_present(self):
        data = QuestionSerializer(self.q).data
        self.assertIn('correct_answer', data)
        self.assertEqual(data['correct_answer'], ['a'])

    def test_correct_flag_present_in_options(self):
        data = QuestionSerializer(self.q).data
        self.assertTrue(any(opt.get('correct') for opt in data['options']))


# ---------------------------------------------------------------------------
# P3 — Validation stricte des questions
# ---------------------------------------------------------------------------
class QuestionWriteValidationTestCase(TestCase):

    def _ser(self, data):
        return QuestionWriteSerializer(data=data)

    def test_qcm_requires_options(self):
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_SINGLE,
            'text': 'Q', 'points': 5, 'options': [],
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('options', ser.errors)

    def test_qcm_requires_at_least_2_options(self):
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_SINGLE,
            'text': 'Q', 'points': 5,
            'options': [{'id': 'a', 'label': 'A', 'correct': True}],
        })
        self.assertFalse(ser.is_valid())

    def test_qcm_rejects_duplicate_option_ids(self):
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_MULTI,
            'text': 'Q', 'points': 5,
            'options': [
                {'id': 'a', 'label': 'A', 'correct': True},
                {'id': 'a', 'label': 'A2'},  # doublon
            ],
        })
        self.assertFalse(ser.is_valid())

    def test_qcm_single_rejects_multiple_correct(self):
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_SINGLE,
            'text': 'Q', 'points': 5,
            'options': [
                {'id': 'a', 'label': 'A', 'correct': True},
                {'id': 'b', 'label': 'B', 'correct': True},
            ],
        })
        self.assertFalse(ser.is_valid())

    def test_qcm_without_correct_marker_rejected(self):
        """Une QCM sans aucune option marquée correcte ET sans correct_answer = piège."""
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_SINGLE,
            'text': 'Q', 'points': 5,
            'options': [
                {'id': 'a', 'label': 'A'},
                {'id': 'b', 'label': 'B'},
            ],
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('correct_answer', ser.errors)

    def test_qcm_with_correct_answer_field_ok(self):
        ser = self._ser({
            'question_type': Question.QuestionType.QCM_SINGLE,
            'text': 'Q', 'points': 5,
            'options': [
                {'id': 'a', 'label': 'A'},
                {'id': 'b', 'label': 'B'},
            ],
            'correct_answer': ['a'],
        })
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_numeric_requires_correct_answer(self):
        ser = self._ser({
            'question_type': Question.QuestionType.NUMERIC,
            'text': 'Q', 'points': 5,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('correct_answer', ser.errors)

    def test_numeric_correct_answer_must_be_number(self):
        ser = self._ser({
            'question_type': Question.QuestionType.NUMERIC,
            'text': 'Q', 'points': 5, 'correct_answer': 'pas un nombre',
        })
        self.assertFalse(ser.is_valid())

    def test_numeric_negative_tolerance_rejected(self):
        ser = self._ser({
            'question_type': Question.QuestionType.NUMERIC,
            'text': 'Q', 'points': 5, 'correct_answer': 42,
            'numeric_tolerance': -0.5,
        })
        self.assertFalse(ser.is_valid())

    def test_true_false_requires_correct_answer(self):
        ser = self._ser({
            'question_type': Question.QuestionType.TRUE_FALSE,
            'text': 'Q', 'points': 5,
        })
        self.assertFalse(ser.is_valid())

    def test_points_must_be_at_least_one(self):
        ser = self._ser({
            'question_type': Question.QuestionType.OPEN_TEXT,
            'text': 'Q', 'points': 0,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('points', ser.errors)

    def test_open_text_minimal_valid(self):
        ser = self._ser({
            'question_type': Question.QuestionType.OPEN_TEXT,
            'text': 'Expliquez', 'points': 10,
        })
        self.assertTrue(ser.is_valid(), ser.errors)


# ---------------------------------------------------------------------------
# P3 — Validation TestWriteSerializer
# ---------------------------------------------------------------------------
class TestWriteValidationTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company, cls.job, _ = _make_test()

    def test_duration_zero_rejected(self):
        ser = TestWriteSerializer(data={
            'title': 'T', 'duration_minutes': 0,
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('duration_minutes', ser.errors)

    def test_negative_passing_score_rejected(self):
        ser = TestWriteSerializer(data={
            'title': 'T', 'passing_score': '-5.00',
        })
        self.assertFalse(ser.is_valid())

    def test_no_duration_ok(self):
        ser = TestWriteSerializer(data={'title': 'Sans timer'})
        self.assertTrue(ser.is_valid(), ser.errors)
