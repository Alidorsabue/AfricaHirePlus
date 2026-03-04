"""
Tests unitaires ATS : services (présélection, sélection, KPI, simulate, PDF) et permissions.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from apps.companies.models import Company
from apps.users.models import User
from apps.jobs.models import JobOffer, PreselectionSettings, ScreeningRule, SelectionSettings
from apps.candidates.models import Candidate
from apps.applications.models import Application
from apps.jobs.services import (
    close_offer,
    compute_preselection,
    compute_selection,
    compute_screening_score,
    simulate_selection,
    compute_kpi,
    generate_shortlist_xlsx,
)


class ATSServicesTestCase(TestCase):
    """Tests des services ATS (jobs + applications)."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Co')
        self.user = User.objects.create_user(
            username='recruiter@test.com',
            email='recruiter@test.com',
            password='test',
            first_name='R',
            last_name='User',
            role='recruiter',
            company=self.company,
        )
        self.job = JobOffer.objects.create(
            company=self.company,
            title='Dev',
            slug='dev-1',
            description='Desc',
            status=JobOffer.Status.PUBLISHED,
            created_by=self.user,
        )
        self.candidate = Candidate.objects.create(
            company=self.company,
            email='cand@test.com',
            first_name='C',
            last_name='Cand',
            raw_cv_text='Python Django',
            skills=['Python'],
            experience_years=3,
        )

    def test_close_offer(self):
        close_offer(self.job)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, JobOffer.Status.CLOSED)
        self.assertIsNotNone(self.job.closed_at)

    def test_compute_screening_score(self):
        ScreeningRule.objects.create(
            job_offer=self.job,
            rule_type=ScreeningRule.RuleType.KEYWORDS,
            value={'keywords': ['Python', 'Django']},
            weight=1,
            order=0,
        )
        app = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.APPLIED,
        )
        score = compute_screening_score(app)
        self.assertIsNotNone(score)
        self.assertGreaterEqual(float(score), 0)

    def test_compute_preselection_sets_status(self):
        PreselectionSettings.objects.create(
            job_offer=self.job,
            score_threshold=50.0,
        )
        ScreeningRule.objects.create(
            job_offer=self.job,
            rule_type=ScreeningRule.RuleType.KEYWORDS,
            value={'keywords': ['Python']},
            weight=1,
            order=0,
        )
        app = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.APPLIED,
        )
        compute_preselection(app)
        app.refresh_from_db()
        self.assertIsNotNone(app.preselection_score)
        self.assertIn(
            app.status,
            (Application.Status.PRESELECTED, Application.Status.REJECTED_PRESELECTION),
        )

    def test_compute_kpi_empty(self):
        kpi = compute_kpi(self.job)
        self.assertEqual(kpi['total_applications'], 0)
        self.assertEqual(kpi['total_preselected'], 0)
        self.assertEqual(kpi['rejection_rate_preselection'], 0.0)

    def test_compute_kpi_with_applications(self):
        app1 = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.PRESELECTED,
            preselection_score=70.0,
        )
        c2 = Candidate.objects.create(
            company=self.company,
            email='c2@test.com',
            first_name='C2',
            last_name='X',
        )
        app2 = Application.objects.create(
            job_offer=self.job,
            candidate=c2,
            status=Application.Status.REJECTED_PRESELECTION,
            preselection_score=40.0,
        )
        kpi = compute_kpi(self.job)
        self.assertEqual(kpi['total_applications'], 2)
        self.assertEqual(kpi['total_preselected'], 1)
        self.assertIsNotNone(kpi['average_preselection_score'])
        self.assertEqual(kpi['highest_score'], 70.0)
        self.assertEqual(kpi['lowest_score'], 40.0)

    def test_simulate_selection(self):
        app = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.PRESELECTED,
            preselection_score=80.0,
        )
        result = simulate_selection(self.job, threshold=60.0, max_candidates=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['application_id'], app.id)
        self.assertEqual(result[0]['rank'], 1)
        self.assertEqual(result[0]['preselection_score'], 80.0)

    def test_compute_selection(self):
        SelectionSettings.objects.create(
            job_offer=self.job,
            score_threshold=50.0,
            max_candidates=5,
        )
        app = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.PRESELECTED,
            preselection_score=75.0,
        )
        shortlisted = compute_selection(self.job)
        self.assertEqual(len(shortlisted), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.SHORTLISTED)

    def test_generate_shortlist_xlsx_returns_bytes(self):
        Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.SHORTLISTED,
            preselection_score=80.0,
            selection_score=80.0,
        )
        out = generate_shortlist_xlsx(self.job, recruiter_name='Test Recruiter')
        self.assertIsInstance(out, bytes)
        self.assertGreater(len(out), 0)
        # Fichier Excel = ZIP (magic bytes PK)
        self.assertTrue(out[:2] == b'PK', 'Contenu Excel (ZIP) attendu')
