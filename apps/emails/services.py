"""
Envoi d'emails automatiques : rendu des templates (variables {{ … }}) et envoi SMTP.
Fonctions : candidature reçue, shortlist, refus.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context

from apps.emails.models import EmailTemplate
from apps.companies.models import Company

logger = logging.getLogger(__name__)


def _render_template(html_content: str, context: dict) -> str:
    """Rend le contenu HTML avec le contexte (candidate_name, job_title, etc.)."""
    try:
        t = Template(html_content)
        return t.render(Context(context))
    except Exception as e:
        logger.warning('Template render failed: %s', e)
        return html_content


def _get_template(company: Company, template_type: str) -> EmailTemplate | None:
    """Retourne le template actif du type donné pour l'entreprise."""
    return EmailTemplate.objects.filter(
        company=company,
        template_type=template_type,
        is_active=True,
    ).first()


def send_application_received(company: Company, candidate_name: str, candidate_email: str, job_title: str):
    """Email de confirmation de réception de candidature."""
    tpl = _get_template(company, EmailTemplate.TemplateType.APPLICATION_RECEIVED)
    if not tpl:
        logger.debug('No template application_received for company %s', company.id)
        return
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject = _render_template(tpl.subject, ctx)
    body = _render_template(tpl.body_html, ctx)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@africahireplus.com',
        recipient_list=[candidate_email],
        html_message=body,
        fail_silently=True,
    )


def send_shortlist_notification(company: Company, candidate_name: str, candidate_email: str, job_title: str):
    """Notification shortlist (candidat pré-sélectionné)."""
    tpl = _get_template(company, EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION)
    if not tpl:
        logger.debug('No template shortlist_notification for company %s', company.id)
        return
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject = _render_template(tpl.subject, ctx)
    body = _render_template(tpl.body_html, ctx)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@africahireplus.com',
        recipient_list=[candidate_email],
        html_message=body,
        fail_silently=True,
    )


def send_rejection_notification(company: Company, candidate_name: str, candidate_email: str, job_title: str):
    """Notification rejet candidature."""
    tpl = _get_template(company, EmailTemplate.TemplateType.APPLICATION_REJECTED)
    if not tpl:
        logger.debug('No template application_rejected for company %s', company.id)
        return
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject = _render_template(tpl.subject, ctx)
    body = _render_template(tpl.body_html, ctx)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@africahireplus.com',
        recipient_list=[candidate_email],
        html_message=body,
        fail_silently=True,
    )
