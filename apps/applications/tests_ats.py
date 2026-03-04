"""
Tests unitaires ATS : manual override, signal présélection.
"""
from django.test import TestCase

from apps.companies.models import Company
from apps.users.models import User
from apps.jobs.models import JobOffer, PreselectionSettings
from apps.candidates.models import Candidate
from apps.applications.models import Application
from apps.applications.services import apply_manual_override


class ApplicationManualOverrideTestCase(TestCase):
    """Tests apply_manual_override."""

    def setUp(self):
        self.company = Company.objects.create(name='Test Co')
        self.job = JobOffer.objects.create(
            company=self.company,
            title='Job',
            slug='job-1',
            description='D',
            status=JobOffer.Status.PUBLISHED,
        )
        self.candidate = Candidate.objects.create(
            company=self.company,
            email='c@test.com',
            first_name='C',
            last_name='C',
        )
        self.app = Application.objects.create(
            job_offer=self.job,
            candidate=self.candidate,
            status=Application.Status.PRESELECTED,
        )

    def test_add_to_shortlist(self):
        apply_manual_override(self.app, 'ADD_TO_SHORTLIST', reason='Bon profil')
        self.app.refresh_from_db()
        self.assertTrue(self.app.is_manually_adjusted)
        self.assertTrue(self.app.manually_added_to_shortlist)
        self.assertEqual(self.app.status, Application.Status.SHORTLISTED)

    def test_remove_from_shortlist(self):
        self.app.status = Application.Status.SHORTLISTED
        self.app.save(update_fields=['status'])
        apply_manual_override(self.app, 'REMOVE_FROM_SHORTLIST', reason='Retrait')
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.REJECTED_SELECTION)
        self.assertFalse(self.app.manually_added_to_shortlist)

    def test_force_status(self):
        apply_manual_override(
            self.app,
            'FORCE_STATUS',
            new_status=Application.Status.HIRED,
            reason='Embauche',
        )
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.HIRED)

    def test_update_score(self):
        apply_manual_override(self.app, 'UPDATE_SCORE', new_score=85.5)
        self.app.refresh_from_db()
        self.assertEqual(self.app.selection_score, 85.5)
