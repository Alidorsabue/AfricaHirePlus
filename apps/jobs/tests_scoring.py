"""
Tests unitaires du moteur de scoring pondéré (scoring_engine).
"""
from django.test import TestCase

from apps.companies.models import Company
from apps.users.models import User
from apps.jobs.models import JobOffer, PreselectionSettings, SelectionSettings
from apps.candidates.models import Candidate
from apps.applications.models import Application
from apps.jobs.scoring_engine import (
    validate_criteria_json,
    compute_weighted_score,
)
from apps.jobs.services import compute_preselection, compute_selection, _compute_selection_score_for_application


class ValidateCriteriaJsonTestCase(TestCase):
    """Validation de la structure criteria_json et somme des poids <= 100."""

    def test_empty_or_none_ok(self):
        validate_criteria_json(None)
        validate_criteria_json({})
        validate_criteria_json({'criteria': None})

    def test_valid_structure(self):
        validate_criteria_json({
            'criteria': [
                {'field': 'experience_years', 'operator': '>=', 'value': 5, 'weight': 50},
                {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 50},
            ],
        })

    def test_sum_over_100_raises(self):
        with self.assertRaises(ValueError) as ctx:
            validate_criteria_json({
                'criteria': [
                    {'field': 'a', 'operator': '=', 'value': 1, 'weight': 60},
                    {'field': 'b', 'operator': '=', 'value': 1, 'weight': 50},
                ],
            })
        self.assertIn('100', str(ctx.exception))

    def test_sum_100_ok(self):
        validate_criteria_json({
            'criteria': [
                {'field': 'a', 'operator': '=', 'value': 1, 'weight': 100},
            ],
        })

    def test_missing_field_raises(self):
        with self.assertRaises(ValueError):
            validate_criteria_json({
                'criteria': [
                    {'operator': '>=', 'value': 5, 'weight': 30},
                ],
            })

    def test_criteria_not_list_raises(self):
        with self.assertRaises(ValueError):
            validate_criteria_json({'criteria': 'not a list'})

    def test_negative_weight_raises(self):
        with self.assertRaises(ValueError):
            validate_criteria_json({
                'criteria': [
                    {'field': 'x', 'operator': '=', 'value': 1, 'weight': -10},
                ],
            })


class ScoringEngineTestCase(TestCase):
    """Tests du calcul de score pondéré et des opérateurs."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Co')
        self.user = User.objects.create_user(
            username='u@test.com',
            email='u@test.com',
            password='test',
            company=self.company,
        )
        self.job = JobOffer.objects.create(
            company=self.company,
            title='Job',
            slug='job-1',
            description='D',
            status=JobOffer.Status.PUBLISHED,
            created_by=self.user,
        )
        self.candidate = Candidate.objects.create(
            company=self.company,
            email='c@test.com',
            first_name='C',
            last_name='C',
            experience_years=6,
            education_level='Master',
        )
        self.application = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.APPLIED,
        )

    def test_compute_weighted_score_empty_criteria(self):
        result = compute_weighted_score(self.application, None)
        self.assertEqual(result['total_score'], 0.0)
        self.assertEqual(result['details'], [])

        result = compute_weighted_score(self.application, {})
        self.assertEqual(result['total_score'], 0.0)

    def test_compute_weighted_score_ge_and_equals(self):
        criteria = {
            'criteria': [
                {'field': 'years_experience', 'operator': '>=', 'value': 5, 'weight': 30},
                {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 25},
                {'field': 'experience_years', 'operator': '>=', 'value': 3, 'weight': 45},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 100.0)
        self.assertEqual(len(result['details']), 3)
        for d in result['details']:
            self.assertTrue(d['passed'], d)
            self.assertIn(d['criterion'], ('years_experience', 'education_level', 'experience_years'))

    def test_compute_weighted_score_partial_pass(self):
        self.candidate.experience_years = 2
        self.candidate.education_level = 'Licence'
        self.candidate.save()
        criteria = {
            'criteria': [
                {'field': 'experience_years', 'operator': '>=', 'value': 5, 'weight': 50},
                {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 50},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 0.0)
        self.assertEqual(len(result['details']), 2)
        for d in result['details']:
            self.assertFalse(d['passed'])

    def test_mandatory_fail_zero_score(self):
        criteria = {
            'criteria': [
                {'field': 'experience_years', 'operator': '>=', 'value': 10, 'weight': 30, 'type': 'mandatory'},
                {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 70},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 0.0)
        self.assertEqual(len(result['details']), 1)

    def test_operator_contains(self):
        self.candidate.summary = 'Python Django AWS'
        self.candidate.save()
        criteria = {
            'criteria': [
                {'field': 'summary', 'operator': 'contains', 'value': 'Django', 'weight': 100},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 100.0)

    def test_operator_in(self):
        criteria = {
            'criteria': [
                {'field': 'education_level', 'operator': 'in', 'value': ['Master', 'Doctorat'], 'weight': 100},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 100.0)

    def test_operator_equals_and_strict(self):
        """Opérateurs =, <, >."""
        self.candidate.experience_years = 5
        self.candidate.save()
        criteria = {
            'criteria': [
                {'field': 'experience_years', 'operator': '=', 'value': 5, 'weight': 50},
                {'field': 'experience_years', 'operator': '<', 'value': 10, 'weight': 25},
                {'field': 'experience_years', 'operator': '>', 'value': 3, 'weight': 25},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertEqual(result['total_score'], 100.0)
        self.assertEqual(len(result['details']), 3)
        for d in result['details']:
            self.assertTrue(d['passed'], d)

    def test_interpretability_details(self):
        """Retour total_score + details pour transparence RH."""
        criteria = {
            'criteria': [
                {'field': 'experience_years', 'operator': '>=', 'value': 5, 'weight': 60},
                {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 40},
            ],
        }
        result = compute_weighted_score(self.application, criteria)
        self.assertIn('total_score', result)
        self.assertIn('details', result)
        self.assertEqual(result['total_score'], 100.0)
        self.assertEqual(len(result['details']), 2)
        self.assertEqual(
            [d['criterion'] for d in result['details']],
            ['experience_years', 'education_level'],
        )
        self.assertEqual([d['weight_awarded'] for d in result['details']], [60.0, 40.0])


class PreselectionIntegrationTestCase(TestCase):
    """Intégration présélection avec criteria_json."""

    def setUp(self):
        self.company = Company.objects.create(name='Co')
        self.user = User.objects.create_user(
            username='r@test.com', email='r@test.com', password='x', company=self.company,
        )
        self.job = JobOffer.objects.create(
            company=self.company,
            title='Dev',
            slug='dev-1',
            description='D',
            status=JobOffer.Status.PUBLISHED,
            created_by=self.user,
        )
        self.candidate = Candidate.objects.create(
            company=self.company,
            email='c@test.com',
            first_name='C',
            last_name='C',
            experience_years=5,
            education_level='Master',
        )
        self.application = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.APPLIED,
        )

    def test_preselection_uses_weighted_criteria(self):
        PreselectionSettings.objects.create(
            job_offer=self.job,
            score_threshold=60.0,
            criteria_json={
                'criteria': [
                    {'field': 'experience_years', 'operator': '>=', 'value': 3, 'weight': 50},
                    {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 50},
                ],
            },
        )
        score = compute_preselection(self.application)
        self.assertIsNotNone(score)
        self.assertEqual(score, 100.0)
        self.application.refresh_from_db()
        self.assertEqual(self.application.preselection_score, 100.0)
        self.assertEqual(self.application.status, Application.Status.PRESELECTED)
        self.assertIsNotNone(self.application.preselection_score_details)
        self.assertEqual(len(self.application.preselection_score_details), 2)
        for d in self.application.preselection_score_details:
            self.assertIn('criterion', d)
            self.assertIn('passed', d)
            self.assertIn('weight_awarded', d)

    def test_preselection_below_threshold_rejected(self):
        PreselectionSettings.objects.create(
            job_offer=self.job,
            score_threshold=80.0,
            criteria_json={
                'criteria': [
                    {'field': 'experience_years', 'operator': '>=', 'value': 10, 'weight': 100},
                ],
            },
        )
        score = compute_preselection(self.application)
        self.assertIsNotNone(score)
        self.assertEqual(score, 0.0)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, Application.Status.REJECTED_PRESELECTION)


class SelectionIntegrationTestCase(TestCase):
    """Intégration sélection avec criteria_json."""

    def setUp(self):
        self.company = Company.objects.create(name='Co')
        self.user = User.objects.create_user(
            username='r@test.com', email='r@test.com', password='x', company=self.company,
        )
        self.job = JobOffer.objects.create(
            company=self.company,
            title='Dev',
            slug='dev-2',
            description='D',
            status=JobOffer.Status.PUBLISHED,
            created_by=self.user,
        )
        self.candidate = Candidate.objects.create(
            company=self.company,
            email='c@test.com',
            first_name='C',
            last_name='C',
            experience_years=7,
            education_level='Master',
        )
        self.application = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.PRESELECTED,
            preselection_score=70.0,
        )

    def test_selection_uses_weighted_criteria(self):
        SelectionSettings.objects.create(
            job_offer=self.job,
            score_threshold=50.0,
            criteria_json={
                'criteria': [
                    {'field': 'experience_years', 'operator': '>=', 'value': 5, 'weight': 60},
                    {'field': 'education_level', 'operator': 'equals', 'value': 'Master', 'weight': 40},
                ],
            },
        )
        shortlisted = compute_selection(self.job)
        self.application.refresh_from_db()
        self.assertEqual(self.application.selection_score, 100.0)
        self.assertEqual(self.application.status, Application.Status.SHORTLISTED)
        self.assertIn(self.application, shortlisted)
        self.assertIsNotNone(self.application.selection_score_details)
        self.assertEqual(len(self.application.selection_score_details), 2)

    def test_selection_score_tuple_return(self):
        """_compute_selection_score_for_application retourne (score, details)."""
        SelectionSettings.objects.create(
            job_offer=self.job,
            criteria_json={
                'criteria': [
                    {'field': 'experience_years', 'operator': '>=', 'value': 5, 'weight': 100},
                ],
            },
        )
        score, details = _compute_selection_score_for_application(self.application)
        self.assertEqual(score, 100.0)
        self.assertIsNotNone(details)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['criterion'], 'experience_years')
        self.assertTrue(details[0]['passed'])
        self.assertEqual(details[0]['weight_awarded'], 100.0)
