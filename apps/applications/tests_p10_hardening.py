"""
Tests P10 — Renforcement candidatures & candidats.

Couvre :
- A1 Sécurité : permissions strictes (candidat bloqué sur endpoints recruteur)
- A2 Serializer : impossible de modifier scores via write serializer
- A3 Audit log : créé lors d'un changement de statut ou override
- A4 Workflow : transitions interdites refusées + withdraw candidat
- A6 Email lowercase normalisé
- A7 RGPD : MyApplicationsListView masque les champs internes / export "mes données" / anonymisation
- A9 Notes internes + tags + bulk-status
"""
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.applications.models import Application, ApplicationAuditLog, ApplicationNote
from apps.applications.services import (
    transition_status,
    InvalidStatusTransition,
    withdraw_application,
    apply_manual_override,
)
from apps.candidates.models import Candidate
from apps.companies.models import Company
from apps.jobs.models import JobOffer

User = get_user_model()


def _username_for(email: str) -> str:
    return email.replace('@', '_').replace('.', '_')


def _make_recruiter(company: Company, email='recruiter@example.com'):
    return User.objects.create_user(
        username=_username_for(email),
        email=email,
        password='pwd-p10',
        role='recruiter',
        company=company,
    )


def _make_candidate_user(email='candidate@example.com'):
    return User.objects.create_user(
        username=_username_for(email),
        email=email,
        password='pwd-p10',
        role='candidate',
    )


def _make_job(company: Company, slug='dev-fullstack-p10'):
    return JobOffer.objects.create(
        company=company,
        title='Développeur Full-stack',
        slug=slug,
        description='Description du poste.',
        status=JobOffer.Status.PUBLISHED,
    )


class PermissionsHardeningTestCase(TestCase):
    """A1 — Un candidat NE PEUT PAS accéder aux endpoints recruteur."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.cand_user = _make_candidate_user()
        self.client = APIClient()

    def test_candidate_cannot_list_applications(self):
        self.client.force_authenticate(self.cand_user)
        resp = self.client.get('/api/v1/applications/')
        self.assertEqual(resp.status_code, 403)

    def test_candidate_cannot_list_candidates_pool(self):
        self.client.force_authenticate(self.cand_user)
        resp = self.client.get('/api/v1/candidates/')
        self.assertEqual(resp.status_code, 403)

    def test_candidate_cannot_create_candidate_in_pool(self):
        self.client.force_authenticate(self.cand_user)
        resp = self.client.post('/api/v1/candidates/', {
            'company': self.company.pk,
            'email': 'attacker@example.com',
            'first_name': 'A', 'last_name': 'B',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_recruiter_can_list_applications(self):
        self.client.force_authenticate(self.recruiter)
        resp = self.client.get('/api/v1/applications/')
        self.assertEqual(resp.status_code, 200)


class WriteSerializerRestrictionTestCase(TestCase):
    """A2 — Les scores/flags ne sont PAS modifiables via le write serializer."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.job = _make_job(self.company)
        self.cand = Candidate.objects.create(
            company=self.company, email='c@a.com', first_name='C', last_name='C',
        )
        self.app = Application.objects.create(
            job_offer=self.job, candidate=self.cand,
            status=Application.Status.APPLIED,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.recruiter)

    def test_score_field_is_ignored_on_write(self):
        url = f'/api/v1/applications/{self.app.pk}/'
        resp = self.client.patch(url, {
            'preselection_score': 99.9,
            'selection_score': 99.9,
            'is_manually_adjusted': True,
            'manual_override_reason': 'TRY TO BYPASS',
        }, format='json')
        # Pas d'erreur (champs en read_only sont ignorés silencieusement par DRF)
        self.assertIn(resp.status_code, (200, 202))
        self.app.refresh_from_db()
        # Les scores ne doivent PAS contenir la valeur frauduleuse 99.9
        # (peuvent valoir None ou 0.0 selon le signal post_save de présélection).
        self.assertNotEqual(self.app.preselection_score, 99.9)
        self.assertNotEqual(self.app.selection_score, 99.9)
        self.assertFalse(self.app.is_manually_adjusted)
        self.assertEqual(self.app.manual_override_reason or '', '')


class WorkflowStateMachineTestCase(TestCase):
    """A4 — Transitions interdites + retrait candidat."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.job = _make_job(self.company)
        self.cand_user = _make_candidate_user()
        self.cand = Candidate.objects.create(
            company=self.company, email=self.cand_user.email,
            first_name='C', last_name='C', user=self.cand_user,
        )
        self.app = Application.objects.create(
            job_offer=self.job, candidate=self.cand,
            status=Application.Status.APPLIED,
        )

    def test_invalid_transition_raises(self):
        with self.assertRaises(InvalidStatusTransition):
            transition_status(self.app, Application.Status.HIRED, actor=self.recruiter)

    def test_valid_transition_logs_audit(self):
        transition_status(self.app, Application.Status.PRESELECTED, actor=self.recruiter, reason='Bon score')
        self.assertEqual(self.app.status, Application.Status.PRESELECTED)
        log = ApplicationAuditLog.objects.filter(application=self.app).latest('created_at')
        self.assertEqual(log.action, ApplicationAuditLog.Action.STATUS_CHANGE)
        self.assertEqual(log.payload_after['status'], Application.Status.PRESELECTED)
        self.assertEqual(log.payload_before['status'], Application.Status.APPLIED)
        self.assertEqual(log.actor, self.recruiter)

    def test_candidate_can_withdraw_own_application(self):
        client = APIClient()
        client.force_authenticate(self.cand_user)
        resp = client.post(f'/api/v1/applications/{self.app.pk}/withdraw/', {'reason': 'plus dispo'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.WITHDRAWN)
        # Audit log présent
        self.assertTrue(ApplicationAuditLog.objects.filter(
            application=self.app, action=ApplicationAuditLog.Action.STATUS_CHANGE,
        ).exists())

    def test_candidate_cannot_withdraw_someone_else(self):
        other_user = _make_candidate_user('other@example.com')
        client = APIClient()
        client.force_authenticate(other_user)
        resp = client.post(f'/api/v1/applications/{self.app.pk}/withdraw/', format='json')
        self.assertEqual(resp.status_code, 404)

    def test_cannot_withdraw_terminal_status(self):
        self.app.status = Application.Status.HIRED
        self.app.save()
        with self.assertRaises(InvalidStatusTransition):
            withdraw_application(self.app, actor=self.cand_user)


class ManualOverrideAuditTestCase(TestCase):
    """A3 — Override manuel trace dans audit log."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.job = _make_job(self.company)
        self.cand = Candidate.objects.create(
            company=self.company, email='c@a.com', first_name='C', last_name='C',
        )
        self.app = Application.objects.create(
            job_offer=self.job, candidate=self.cand,
            status=Application.Status.APPLIED,
        )

    def test_manual_override_creates_audit(self):
        apply_manual_override(
            self.app, 'UPDATE_SCORE', new_score=85.5, reason='Très bon entretien',
            actor=self.recruiter,
        )
        self.app.refresh_from_db()
        self.assertEqual(self.app.selection_score, 85.5)
        self.assertTrue(self.app.is_manually_adjusted)
        log = ApplicationAuditLog.objects.filter(
            application=self.app, action=ApplicationAuditLog.Action.MANUAL_OVERRIDE,
        ).latest('created_at')
        self.assertEqual(log.payload_after['selection_score'], 85.5)
        self.assertEqual(log.reason, 'Très bon entretien')
        self.assertEqual(log.actor, self.recruiter)


class CandidateEmailNormalizationTestCase(TestCase):
    """A6 — Email normalisé en lowercase au save."""

    def test_email_lowercased_on_save(self):
        company = Company.objects.create(name='Co')
        c = Candidate.objects.create(
            company=company, email='ALICE@Example.COM', first_name='A', last_name='B',
        )
        c.refresh_from_db()
        self.assertEqual(c.email, 'alice@example.com')

    def test_unique_constraint_with_normalization(self):
        company = Company.objects.create(name='Co')
        Candidate.objects.create(company=company, email='Bob@X.com', first_name='B', last_name='B')
        # Doublon avec casse différente : doit échouer
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Candidate.objects.create(company=company, email='bob@x.com', first_name='B2', last_name='B2')


class CandidateRgpdTestCase(TestCase):
    """A7 — RGPD : anonymisation + export 'mes données' + masquage scores internes côté candidat."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.cand_user = _make_candidate_user()
        self.cand = Candidate.objects.create(
            company=self.company, email=self.cand_user.email,
            first_name='Alice', last_name='Doe', user=self.cand_user,
            linkedin_url='https://linkedin.com/in/alice',
        )
        self.job = _make_job(self.company)
        self.app = Application.objects.create(
            job_offer=self.job, candidate=self.cand,
            status=Application.Status.SHORTLISTED,
            preselection_score=87.5,
            preselection_score_details={'criteria': ['secret']},
            notes='Note interne recruteur',
            manual_override_reason='Aurait dû être rejeté mais bon test',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.cand_user)

    def test_mine_endpoint_strips_internal_fields(self):
        resp = self.client.get('/api/v1/applications/mine/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        items = body['results'] if isinstance(body, dict) and 'results' in body else body
        self.assertTrue(items)
        item = items[0]
        # Champs internes interdits côté candidat
        self.assertNotIn('preselection_score', item)
        self.assertNotIn('preselection_score_details', item)
        self.assertNotIn('selection_score_details', item)
        self.assertNotIn('manual_override_reason', item)
        self.assertNotIn('notes', item)
        # Champs autorisés
        self.assertIn('status', item)
        self.assertIn('applied_at', item)

    def test_export_my_data_returns_json(self):
        resp = self.client.get('/api/v1/candidates/me/export/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('user', data)
        self.assertIn('candidates', data)
        self.assertEqual(len(data['candidates']), 1)
        self.assertEqual(data['candidates'][0]['email'], self.cand.email)
        self.assertEqual(len(data['candidates'][0]['applications']), 1)

    def test_anonymize_via_me_endpoint(self):
        resp = self.client.delete('/api/v1/candidates/me/')
        self.assertEqual(resp.status_code, 200)
        self.cand.refresh_from_db()
        self.assertTrue(self.cand.is_anonymized)
        self.assertIsNotNone(self.cand.anonymized_at)
        self.assertEqual(self.cand.first_name, '(anonymisé)')
        self.assertIsNone(self.cand.user_id)
        # Mais la candidature existe toujours pour audit
        self.assertTrue(Application.objects.filter(pk=self.app.pk).exists())


class FileValidationTestCase(TestCase):
    """A2 — Validation des fichiers (taille, MIME, extension)."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.job = _make_job(self.company)
        self.cand_user = _make_candidate_user()
        self.client = APIClient()
        self.client.force_authenticate(self.cand_user)

    def test_dangerous_extension_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        evil = SimpleUploadedFile('virus.exe', b'MZ\x90\x00', content_type='application/octet-stream')
        resp = self.client.post('/api/v1/applications/public/apply/', {
            'job_offer_slug': self.job.slug,
            'first_name': 'X', 'last_name': 'Y',
            'resume': evil,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        # Le custom exception handler enveloppe l'erreur dans {error: {details: {...}}}
        details = body.get('error', {}).get('details', body)
        self.assertIn('resume', details, msg=f"Réponse inattendue: {body}")

    def test_oversized_file_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        big = SimpleUploadedFile(
            'cv.pdf',
            b'A' * (11 * 1024 * 1024),  # 11 Mo > 10 Mo max
            content_type='application/pdf',
        )
        resp = self.client.post('/api/v1/applications/public/apply/', {
            'job_offer_slug': self.job.slug,
            'first_name': 'X', 'last_name': 'Y',
            'resume': big,
        }, format='multipart')
        self.assertEqual(resp.status_code, 400)


class TagsAndBulkStatusTestCase(TestCase):
    """A9 — Tags candidat + bulk-status candidatures."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.job = _make_job(self.company)
        self.cands = [
            Candidate.objects.create(
                company=self.company, email=f'c{i}@a.com', first_name=f'C{i}', last_name='X',
            )
            for i in range(3)
        ]
        self.apps = [
            Application.objects.create(
                job_offer=self.job, candidate=c, status=Application.Status.APPLIED,
            )
            for c in self.cands
        ]
        self.client = APIClient()
        self.client.force_authenticate(self.recruiter)

    def test_set_candidate_tags(self):
        c = self.cands[0]
        resp = self.client.patch(f'/api/v1/candidates/{c.pk}/tags/', {
            'tags': ['top-talent', 'remote-ok', 'top-talent', '   '],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        c.refresh_from_db()
        self.assertEqual(sorted(c.tags), ['remote-ok', 'top-talent'])

    def test_bulk_status_transitions_with_errors(self):
        ids = [a.pk for a in self.apps]
        resp = self.client.post('/api/v1/applications/bulk-status/', {
            'application_ids': ids,
            'status': Application.Status.PRESELECTED,
            'reason': 'Auto-batch',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body['updated']), 3)
        # Maintenant tenter HIRED depuis PRESELECTED → interdit
        resp2 = self.client.post('/api/v1/applications/bulk-status/', {
            'application_ids': ids,
            'status': Application.Status.HIRED,
        }, format='json')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.json()['updated']), 0)
        self.assertEqual(len(resp2.json()['errors']), 3)

    def test_bulk_status_anti_dos_limit(self):
        resp = self.client.post('/api/v1/applications/bulk-status/', {
            'application_ids': list(range(1, 600)),
            'status': Application.Status.PRESELECTED,
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class InternalNoteTestCase(TestCase):
    """A9 — Notes internes recruteur (jamais exposées au candidat)."""

    def setUp(self):
        self.company = Company.objects.create(name='Acme')
        self.recruiter = _make_recruiter(self.company)
        self.cand_user = _make_candidate_user()
        self.cand = Candidate.objects.create(
            company=self.company, email=self.cand_user.email,
            first_name='C', last_name='C', user=self.cand_user,
        )
        self.job = _make_job(self.company)
        self.app = Application.objects.create(
            job_offer=self.job, candidate=self.cand,
            status=Application.Status.SHORTLISTED,
        )

    def test_recruiter_can_add_internal_note(self):
        client = APIClient()
        client.force_authenticate(self.recruiter)
        resp = client.post(f'/api/v1/applications/{self.app.pk}/notes/', {
            'body': 'Profil intéressant, à rappeler.', 'is_pinned': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        note = ApplicationNote.objects.get(application=self.app)
        self.assertEqual(note.body, 'Profil intéressant, à rappeler.')
        self.assertEqual(note.author, self.recruiter)
        self.assertTrue(note.is_pinned)

    def test_candidate_cannot_access_internal_notes(self):
        ApplicationNote.objects.create(
            application=self.app, author=self.recruiter, body='Secret recruteur',
        )
        client = APIClient()
        client.force_authenticate(self.cand_user)
        resp = client.get(f'/api/v1/applications/{self.app.pk}/notes/')
        self.assertEqual(resp.status_code, 403)

    def test_empty_note_rejected(self):
        client = APIClient()
        client.force_authenticate(self.recruiter)
        resp = client.post(f'/api/v1/applications/{self.app.pk}/notes/', {
            'body': '   ',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
