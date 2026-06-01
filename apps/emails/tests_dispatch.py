"""
Tests P9 — Pipeline d'envoi d'emails (dispatch + branding + Brevo backend).

Couverture :
  - dispatch_email() crée un EmailLog correctement
  - HTML branded est généré (wrapper + bouton CTA)
  - Le backend `locmem` reçoit le message
  - BrevoApiBackend convertit correctement EmailMessage → payload Brevo
  - Mode SKIPPED si destinataire invalide
  - Mode FAILED si backend lève
"""
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.companies.models import Company
from apps.emails.backends import BrevoApiBackend
from apps.emails.branding import html_to_text, render_branded_html
from apps.emails.dispatch import dispatch_email
from apps.emails.models import EmailLog


def _make_company():
    return Company.objects.create(
        name='AcmeEmail',
        slug=f'acmeemail-{timezone.now().timestamp()}',
        email='hr@acme.com',
    )


# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
class BrandingTestCase(TestCase):

    def test_html_to_text_strips_tags(self):
        html = '<p>Bonjour <strong>Jean</strong>!</p><p>Lien : <a href="https://x.io">ici</a></p>'
        text = html_to_text(html)
        self.assertIn('Bonjour Jean', text)
        self.assertIn('https://x.io', text)
        self.assertNotIn('<strong>', text)

    def test_render_branded_html_includes_cta_button(self):
        html = render_branded_html(
            company_name='Acme',
            body_html='<p>Test</p>',
            cta_label='Cliquer ici',
            cta_url='https://example.com/x',
        )
        self.assertIn('Cliquer ici', html)
        self.assertIn('https://example.com/x', html)
        self.assertIn('Acme', html)  # header

    def test_render_branded_html_preheader_hidden(self):
        html = render_branded_html(
            company_name='Acme', body_html='<p>Hi</p>',
            preheader='aperçu boîte de réception',
        )
        self.assertIn('aperçu boîte de réception', html)
        # Preheader doit être en display:none
        self.assertIn('display:none', html)


# ---------------------------------------------------------------------------
# dispatch_email
# ---------------------------------------------------------------------------
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DispatchEmailTestCase(TestCase):

    def setUp(self):
        mail.outbox = []
        self.company = _make_company()

    def test_dispatch_creates_log_and_sends(self):
        log = dispatch_email(
            company=self.company,
            template_type='test_invitation',
            recipient='john@ex.com',
            subject='Hello',
            body_html='<p>Test body</p>',
            cta_label='Open', cta_url='https://app/x',
        )
        self.assertIsNotNone(log)
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.recipient_email, 'john@ex.com')
        self.assertEqual(log.template_type, 'test_invitation')
        self.assertEqual(log.attempts, 1)
        # 1 email dans la outbox locmem
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.to, ['john@ex.com'])
        # body text + alternative html
        self.assertEqual(m.alternatives[0][1], 'text/html')
        self.assertIn('Open', m.alternatives[0][0])
        self.assertIn('https://app/x', m.alternatives[0][0])

    def test_dispatch_skipped_if_invalid_recipient(self):
        log = dispatch_email(
            company=self.company, template_type='custom',
            recipient='', subject='X', body_html='<p>X</p>',
        )
        self.assertEqual(log.status, EmailLog.Status.SKIPPED)
        self.assertEqual(len(mail.outbox), 0)

    def test_dispatch_failed_on_backend_error(self):
        with patch(
            'apps.emails.dispatch.get_connection',
        ) as mocked:
            mocked.return_value.send_messages.side_effect = RuntimeError('boom')
            log = dispatch_email(
                company=self.company, template_type='custom',
                recipient='x@ex.com', subject='X', body_html='<p>X</p>',
            )
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertIn('boom', log.error_message)

    @override_settings(EMAIL_AUDIT_LOG_ENABLED=False)
    def test_dispatch_no_audit_when_disabled(self):
        log = dispatch_email(
            company=self.company, template_type='custom',
            recipient='x@ex.com', subject='X', body_html='<p>X</p>',
        )
        self.assertIsNone(log)
        self.assertEqual(EmailLog.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_dispatch_uses_company_from(self):
        dispatch_email(
            company=self.company, template_type='custom',
            recipient='x@ex.com', subject='X', body_html='<p>X</p>',
        )
        m = mail.outbox[0]
        self.assertIn('hr@acme.com', m.from_email)


# ---------------------------------------------------------------------------
# BrevoApiBackend (sans appel réseau)
# ---------------------------------------------------------------------------
class BrevoApiBackendTestCase(TestCase):

    @override_settings(
        BREVO_API_KEY='test-key',
        EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend',
    )
    def test_payload_construction(self):
        """L'EmailMessage Django est correctement converti en payload Brevo."""
        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(
            subject='Bonjour',
            body='Texte brut',
            from_email='"Acme" <noreply@acme.com>',
            to=['"Jean" <jean@ex.com>'],
            cc=['cc@ex.com'],
            bcc=['bcc@ex.com'],
            reply_to=['support@acme.com'],
            headers={'X-Custom-Header': 'foo'},
        )
        msg.attach_alternative('<p>HTML</p>', 'text/html')
        msg.brevo_tags = ['invitation', 'tier1']

        backend = BrevoApiBackend()
        payload = backend._build_payload(msg)
        self.assertEqual(payload['sender']['email'], 'noreply@acme.com')
        self.assertEqual(payload['sender']['name'], 'Acme')
        self.assertEqual(payload['to'][0]['email'], 'jean@ex.com')
        self.assertEqual(payload['to'][0]['name'], 'Jean')
        self.assertEqual(payload['cc'][0]['email'], 'cc@ex.com')
        self.assertEqual(payload['bcc'][0]['email'], 'bcc@ex.com')
        self.assertEqual(payload['replyTo']['email'], 'support@acme.com')
        self.assertEqual(payload['subject'], 'Bonjour')
        self.assertEqual(payload['htmlContent'], '<p>HTML</p>')
        self.assertEqual(payload['textContent'], 'Texte brut')
        self.assertIn('X-Custom-Header', payload['headers'])
        self.assertEqual(payload['tags'], ['invitation', 'tier1'])

    @override_settings(BREVO_API_KEY='', EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend')
    def test_no_api_key_returns_zero_silent(self):
        from django.core.mail import EmailMessage
        msg = EmailMessage(subject='x', body='x', from_email='a@a', to=['b@b'])
        backend = BrevoApiBackend(fail_silently=True)
        self.assertEqual(backend.send_messages([msg]), 0)

    @override_settings(
        BREVO_API_KEY='k',
        EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend',
    )
    def test_4xx_not_retried(self):
        """Une erreur 400 (domaine non vérifié, etc.) ne doit PAS être retried."""
        from django.core.mail import EmailMessage
        msg = EmailMessage(subject='x', body='x', from_email='a@a.com', to=['b@b.com'])
        backend = BrevoApiBackend(fail_silently=True)
        with patch.object(backend, '_post') as mp:
            from apps.emails.backends import BrevoApiError
            mp.side_effect = BrevoApiError(400, {'message': 'bad'}, retryable=False)
            backend.send_messages([msg])
        self.assertEqual(mp.call_count, 1)

    @override_settings(
        BREVO_API_KEY='k',
        EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend',
    )
    def test_5xx_is_retried(self):
        """Une erreur 503 doit être retried jusqu'à 3 fois."""
        from django.core.mail import EmailMessage
        msg = EmailMessage(subject='x', body='x', from_email='a@a.com', to=['b@b.com'])
        backend = BrevoApiBackend(fail_silently=True)
        with patch.object(backend, '_post') as mp:
            from apps.emails.backends import BrevoApiError
            mp.side_effect = BrevoApiError(503, 'down', retryable=True)
            with patch('apps.emails.backends.time.sleep'):  # éviter les vraies pauses
                backend.send_messages([msg])
        self.assertEqual(mp.call_count, 3)

    @override_settings(
        BREVO_API_KEY='k',
        EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend',
    )
    def test_message_id_captured_on_success(self):
        from django.core.mail import EmailMessage
        msg = EmailMessage(subject='x', body='x', from_email='a@a.com', to=['b@b.com'])
        backend = BrevoApiBackend()
        with patch.object(backend, '_post', return_value={'messageId': '<abc@brevo>'}):
            sent = backend.send_messages([msg])
        self.assertEqual(sent, 1)
        self.assertEqual(msg.extra_headers['X-Brevo-Message-Id'], '<abc@brevo>')
