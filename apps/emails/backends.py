"""
Backend Django pour l'envoi d'emails via l'API HTTP Brevo (anciennement Sendinblue).

Choix d'implémentation :
  - On NE charge PAS le SDK officiel `sib-api-v3-sdk` pour éviter une
    dépendance lourde — un simple `requests.post` suffit.
  - Le backend convertit chaque `EmailMessage`/`EmailMultiAlternatives` Django
    en payload Brevo : sender, to, subject, htmlContent, textContent, attachments,
    headers, replyTo, tags.
  - Le `message_id` Brevo (header X-Message-Id) est attaché à l'objet
    EmailMessage via `extra_headers['X-Brevo-Message-Id']` pour audit
    (utilisé par `dispatch_email` → EmailLog).
  - Retry simple (3 tentatives avec back-off exponentiel) sur les erreurs
    réseau / 5xx — pas sur les 4xx (qui sont fonctionnelles : email invalide,
    domaine non vérifié, etc.).

Documentation Brevo : https://developers.brevo.com/reference/sendtransacemail
"""
from __future__ import annotations

import base64
import logging
import time
from email.utils import getaddresses, parseaddr
from typing import Any

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage, EmailMultiAlternatives

logger = logging.getLogger(__name__)

# Plafonds Brevo (https://developers.brevo.com/docs/transactional-emails)
MAX_RECIPIENTS_PER_CALL = 50  # to + cc + bcc
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 Mo (limite Brevo)


class BrevoApiError(Exception):
    """Erreur retournée par l'API Brevo (avec status code et payload)."""

    def __init__(self, status_code: int, payload: Any, *, retryable: bool = False):
        self.status_code = status_code
        self.payload = payload
        self.retryable = retryable
        super().__init__(f'Brevo API {status_code}: {payload}')


class BrevoApiBackend(BaseEmailBackend):
    """
    Backend transactional email via Brevo HTTP API v3.

    Activation : `EMAIL_BACKEND='apps.emails.backends.BrevoApiBackend'`
    Variables requises : `BREVO_API_KEY`. Optionnelles : `BREVO_API_URL`,
    `BREVO_API_TIMEOUT`.

    `fail_silently=True` (sur EmailMessage ou ici) avale les exceptions
    pour rester compatible avec `send_mail(..., fail_silently=True)`.
    """

    def __init__(self, fail_silently: bool = False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, 'BREVO_API_KEY', '') or ''
        self.api_url = (
            getattr(settings, 'BREVO_API_URL', '') or 'https://api.brevo.com/v3/smtp/email'
        )
        self.timeout = int(getattr(settings, 'BREVO_API_TIMEOUT', 15) or 15)

    # -----------------------------------------------------------------------
    # API publique Django
    # -----------------------------------------------------------------------
    def send_messages(self, email_messages):
        """Envoie une liste d'EmailMessage. Retourne le nombre envoyés OK."""
        if not email_messages:
            return 0
        if not self.api_key:
            logger.error(
                'BrevoApiBackend: BREVO_API_KEY est vide — aucun email envoyé. '
                'Définissez BREVO_API_KEY dans .env ou utilisez un autre backend.'
            )
            if not self.fail_silently:
                raise BrevoApiError(0, 'BREVO_API_KEY manquante', retryable=False)
            return 0

        try:
            import requests  # noqa: F401 — import paresseux
        except ImportError as e:
            logger.error('BrevoApiBackend: requests non installé — %s', e)
            if not self.fail_silently:
                raise
            return 0

        sent = 0
        for message in email_messages:
            try:
                self._send_one(message)
                sent += 1
            except BrevoApiError as e:
                logger.warning(
                    'Brevo: échec envoi à=%s sujet=%r status=%s err=%s',
                    message.to, message.subject, e.status_code, e.payload,
                )
                if not (self.fail_silently or message.fail_silently):
                    raise
            except Exception as e:
                logger.exception(
                    'Brevo: exception inattendue à=%s sujet=%r : %s',
                    message.to, message.subject, e,
                )
                if not (self.fail_silently or message.fail_silently):
                    raise
        return sent

    # -----------------------------------------------------------------------
    # Mécanique interne
    # -----------------------------------------------------------------------
    def _send_one(self, message: EmailMessage) -> dict:
        """Envoie un seul EmailMessage avec retry. Retourne le payload Brevo."""
        payload = self._build_payload(message)
        last_err: BrevoApiError | None = None
        delays = (0.0, 0.8, 2.0)  # 3 tentatives max
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                response = self._post(payload)
                # Succès : attache le messageId Brevo aux extra_headers pour audit
                msg_id = (response or {}).get('messageId') or ''
                if msg_id:
                    if not message.extra_headers:
                        message.extra_headers = {}
                    message.extra_headers['X-Brevo-Message-Id'] = msg_id
                return response or {}
            except BrevoApiError as e:
                last_err = e
                # 4xx (sauf 429) = erreurs fonctionnelles → on n'insiste pas
                if not e.retryable:
                    raise
                logger.info(
                    'Brevo: tentative %d/%d échouée (status=%s, retry...).',
                    attempt, len(delays), e.status_code,
                )
        if last_err:
            raise last_err
        raise BrevoApiError(0, 'unknown error', retryable=False)

    def _post(self, payload: dict) -> dict:
        """POST l'URL Brevo et lève BrevoApiError en cas d'échec."""
        import requests

        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'api-key': self.api_key,
        }
        try:
            r = requests.post(
                self.api_url, json=payload, headers=headers, timeout=self.timeout,
            )
        except requests.RequestException as e:
            # Erreur réseau / timeout → retryable
            raise BrevoApiError(0, f'network: {e}', retryable=True) from e

        if 200 <= r.status_code < 300:
            try:
                return r.json()
            except ValueError:
                return {}

        # Tentative de parser le body d'erreur
        try:
            body = r.json()
        except ValueError:
            body = r.text[:500]

        # Brevo : 429 = rate limit, 5xx = problèmes serveur → retry
        retryable = r.status_code == 429 or 500 <= r.status_code < 600
        raise BrevoApiError(r.status_code, body, retryable=retryable)

    def _build_payload(self, message: EmailMessage) -> dict:
        """Convertit un EmailMessage Django en payload Brevo JSON."""
        from_name, from_email = parseaddr(message.from_email or '')
        sender = {'email': from_email or message.from_email or ''}
        if from_name:
            sender['name'] = from_name

        def _to_brevo_recipients(addrs):
            """Liste 'Nom <a@b.com>' → [{'email':..., 'name':...}, ...]"""
            out = []
            for raw_name, raw_email in getaddresses(list(addrs) or []):
                if not raw_email:
                    continue
                entry = {'email': raw_email}
                if raw_name:
                    entry['name'] = raw_name
                out.append(entry)
            return out

        to_list = _to_brevo_recipients(message.to)
        cc_list = _to_brevo_recipients(message.cc)
        bcc_list = _to_brevo_recipients(message.bcc)
        total = len(to_list) + len(cc_list) + len(bcc_list)
        if total > MAX_RECIPIENTS_PER_CALL:
            raise BrevoApiError(
                400,
                f'Trop de destinataires ({total} > {MAX_RECIPIENTS_PER_CALL})',
                retryable=False,
            )

        # Corps : text + html (priorité aux alternatives sur le body principal)
        text_body = ''
        html_body = ''
        if isinstance(message, EmailMultiAlternatives) and message.alternatives:
            text_body = message.body or ''
            for content, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    html_body = content
                    break
        else:
            ctype = (getattr(message, 'content_subtype', '') or '').lower()
            if ctype == 'html':
                html_body = message.body or ''
            else:
                text_body = message.body or ''

        payload: dict[str, Any] = {
            'sender': sender,
            'to': to_list,
            'subject': message.subject or '(sans objet)',
        }
        if html_body:
            payload['htmlContent'] = html_body
        if text_body:
            payload['textContent'] = text_body
        if cc_list:
            payload['cc'] = cc_list
        if bcc_list:
            payload['bcc'] = bcc_list

        # Reply-To
        reply_to = _to_brevo_recipients(message.reply_to)
        if reply_to:
            payload['replyTo'] = reply_to[0]

        # Headers personnalisés (utile pour tracking/segmentation)
        if message.extra_headers:
            # Brevo : 'headers' = dict de strings
            payload['headers'] = {
                str(k): str(v) for k, v in message.extra_headers.items()
                # Filtre les en-têtes synthétiques internes
                if not str(k).lower().startswith('x-brevo-')
            } or None
            if payload['headers'] is None:
                payload.pop('headers', None)

        # Tags : récupère 'tags' depuis extra_headers ou attribute custom
        tags = getattr(message, 'brevo_tags', None) or (
            (message.extra_headers or {}).get('X-Brevo-Tags')
        )
        if tags:
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            payload['tags'] = list(tags)[:10]  # plafond raisonnable

        # Pièces jointes
        attachments = self._build_attachments(message)
        if attachments:
            payload['attachment'] = attachments

        return payload

    def _build_attachments(self, message: EmailMessage) -> list[dict]:
        """Convertit les attachments Django en format Brevo (base64)."""
        out: list[dict] = []
        for att in getattr(message, 'attachments', None) or []:
            try:
                # Format Django : (filename, content, mimetype) OU MIMEBase
                if isinstance(att, tuple) and len(att) >= 2:
                    name = att[0] or 'attachment'
                    content = att[1]
                else:
                    # MIMEBase : on prend get_filename() + get_payload(decode=True)
                    name = att.get_filename() or 'attachment'
                    content = att.get_payload(decode=True) or b''

                if isinstance(content, str):
                    content = content.encode('utf-8')
                if len(content) > MAX_ATTACHMENT_BYTES:
                    logger.warning(
                        'Brevo: pièce jointe ignorée (taille=%d > %d): %s',
                        len(content), MAX_ATTACHMENT_BYTES, name,
                    )
                    continue
                out.append(
                    {
                        'name': str(name),
                        'content': base64.b64encode(content).decode('ascii'),
                    },
                )
            except Exception as e:
                logger.warning('Brevo: pièce jointe non sérialisable : %s', e)
        return out
