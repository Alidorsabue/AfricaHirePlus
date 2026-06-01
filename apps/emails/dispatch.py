"""
Wrapper unifié `dispatch_email()` : un point d'entrée unique pour tous les
envois transactionnels du projet.

Responsabilités :
  - Construire un `EmailMultiAlternatives` (text + HTML),
  - Créer un `EmailLog` (audit) en `pending`,
  - Tenter l'envoi via le backend Django configuré (Brevo API / SMTP / console),
  - Mettre à jour le log avec le statut final + message-id Brevo,
  - Ne JAMAIS lever d'exception vers l'appelant (best-effort).

Pourquoi un wrapper ? On centralise l'audit, le branding HTML par défaut,
la conversion text/html, et le traitement des erreurs — au lieu d'avoir
9 appels `send_mail()` éparpillés dans le code.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from apps.companies.models import Company
from apps.core.email_utils import get_from_email, get_from_email_for_company

from .branding import html_to_text, render_branded_html
from .models import EmailLog

logger = logging.getLogger(__name__)


def _provider_name() -> str:
    """Identifiant lisible du backend actuel (pour les logs)."""
    backend = (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    if 'brevo' in backend:
        return 'brevo_api'
    if 'smtp' in backend:
        return 'smtp'
    if 'console' in backend:
        return 'console'
    if 'locmem' in backend:
        return 'locmem'
    return backend or 'unknown'


def dispatch_email(
    *,
    company: Optional[Company],
    template_type: str,
    recipient: str,
    subject: str,
    body_html: str,
    body_text: Optional[str] = None,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    preheader: Optional[str] = None,
    footer_note: Optional[str] = None,
    branded: bool = True,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    reply_to: Optional[Iterable[str]] = None,
    headers: Optional[Mapping[str, str]] = None,
    tags: Optional[Iterable[str]] = None,
    related_application_id: Optional[int] = None,
    related_object: Any = None,
) -> EmailLog | None:
    """
    Envoie un email transactionnel et trace l'envoi dans `EmailLog`.

    Args :
      company             : entreprise propriétaire (utilisé pour le From
                            personnalisé + le branding HTML).
      template_type       : identifiant logique (correspond à
                            `EmailTemplate.TemplateType`).
      recipient           : adresse du destinataire principal.
      subject / body_html : sujet + corps HTML (peut contenir des variables
                            déjà rendues).
      body_text           : version texte (déduite automatiquement de body_html
                            si non fournie).
      cta_label / cta_url : si fournis et `branded=True`, un bouton CTA est
                            ajouté au-dessus du footer.
      preheader           : aperçu en boîte de réception (< 100 chars).
      footer_note         : mention complémentaire en pied (raison de l'email).
      branded             : si False, le body_html est envoyé tel quel (utile
                            pour un template DB déjà complet).
      cc/bcc/reply_to     : adresses supplémentaires (listes).
      headers             : headers SMTP/HTTP additionnels.
      tags                : tags Brevo (pour segmentation des stats).
      related_application_id  : ID d'application pour debug (sans FK).
      related_object      : objet déclencheur (typiquement un model Django) ;
                            son type/id sont stockés pour audit.

    Retour : l'objet `EmailLog` créé, ou None si l'audit est désactivé.
    """
    recipient = (recipient or '').strip()
    log: EmailLog | None = None
    audit_enabled = bool(getattr(settings, 'EMAIL_AUDIT_LOG_ENABLED', True))

    related_type, related_id = '', None
    if related_object is not None:
        related_type = related_object.__class__.__name__
        related_id = getattr(related_object, 'pk', None) or getattr(related_object, 'id', None)

    if audit_enabled:
        try:
            log = EmailLog.objects.create(
                company=company,
                template_type=template_type or '',
                recipient_email=recipient or '(invalid)',
                subject=(subject or '')[:255],
                status=EmailLog.Status.PENDING,
                provider=_provider_name(),
                related_application_id=related_application_id,
                related_object_type=related_type,
                related_object_id=related_id,
            )
        except Exception as e:
            # Si la table n'existe pas encore (migration non appliquée) ou DB
            # indisponible, on continue sans audit pour ne pas bloquer l'envoi.
            logger.warning('EmailLog non créé (%s) — envoi sans audit.', e)
            log = None

    # Validation minimale : si le destinataire est invalide, on skip.
    if not recipient or '@' not in recipient:
        _mark_skipped(log, 'Adresse destinataire vide ou invalide.')
        return log

    # Préparation du corps HTML branded (si demandé).
    final_html = body_html
    if branded:
        final_html = render_branded_html(
            company_name=(company.name if company else 'AfricaHire+'),
            company_logo_url=_company_logo_url(company),
            body_html=body_html,
            cta_label=cta_label,
            cta_url=cta_url,
            preheader=preheader,
            footer_note=footer_note,
        )

    # Texte brut : fourni explicitement, sinon dérivé du HTML.
    final_text = body_text if body_text is not None else html_to_text(final_html)
    if not final_text.strip():
        final_text = html_to_text(body_html)

    from_email = get_from_email_for_company(company) if company else get_from_email()

    extra_headers = dict(headers or {})
    msg = EmailMultiAlternatives(
        subject=subject or '(sans objet)',
        body=final_text,
        from_email=from_email,
        to=[recipient],
        cc=list(cc) if cc else None,
        bcc=list(bcc) if bcc else None,
        reply_to=list(reply_to) if reply_to else None,
        headers=extra_headers or None,
    )
    msg.attach_alternative(final_html, 'text/html')
    if tags:
        # Lu par BrevoApiBackend, ignoré par les autres backends (sans effet).
        msg.brevo_tags = list(tags)  # type: ignore[attr-defined]

    if log is not None:
        log.attempts = (log.attempts or 0) + 1
        log.save(update_fields=['attempts'])

    try:
        # `fail_silently=False` ici (au niveau message) pour qu'on RÉCUPÈRE
        # l'exception et la log dans EmailLog. Le wrapper attrape lui-même.
        connection = get_connection(fail_silently=False)
        sent = connection.send_messages([msg])
    except Exception as e:
        logger.warning(
            'dispatch_email: échec envoi à=%s template=%s : %s',
            recipient, template_type, e,
        )
        _mark_failed(log, str(e)[:2000])
        return log

    if sent and sent >= 1:
        provider_id = ''
        if msg.extra_headers:
            provider_id = msg.extra_headers.get('X-Brevo-Message-Id', '') or ''
        _mark_sent(log, provider_id)
    else:
        _mark_failed(log, 'Backend a retourné 0 envoi (cause inconnue).')
    return log


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------
def _mark_sent(log: EmailLog | None, provider_message_id: str) -> None:
    if not log:
        return
    log.status = EmailLog.Status.SENT
    log.sent_at = timezone.now()
    log.provider_message_id = (provider_message_id or '')[:255]
    log.save(update_fields=['status', 'sent_at', 'provider_message_id', 'updated_at'])


def _mark_failed(log: EmailLog | None, message: str) -> None:
    if not log:
        return
    log.status = EmailLog.Status.FAILED
    log.error_message = message or ''
    log.save(update_fields=['status', 'error_message', 'updated_at'])


def _mark_skipped(log: EmailLog | None, message: str) -> None:
    if not log:
        return
    log.status = EmailLog.Status.SKIPPED
    log.error_message = message or ''
    log.save(update_fields=['status', 'error_message', 'updated_at'])


def _company_logo_url(company: Company | None) -> Optional[str]:
    """Récupère l'URL du logo de l'entreprise si disponible et accessible HTTP."""
    if not company:
        return None
    logo = getattr(company, 'logo', None)
    if not logo:
        return None
    try:
        url = logo.url  # peut être un /media/... relatif en dev
    except Exception:
        return None
    if not url:
        return None
    # Brevo / clients mail exigent une URL absolue → on n'envoie le logo
    # que si l'URL est déjà absolue (S3 / CDN configuré). Sinon on l'omet.
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return None
