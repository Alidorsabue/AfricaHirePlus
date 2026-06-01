"""
Helpers e-mail : expéditeur avec nom d’affichage (RFC), utilisé par les envois transactionnels.
"""
from __future__ import annotations

from email.utils import formataddr

from django.conf import settings

from apps.companies.models import Company


def get_from_email() -> str:
    """
    Adresse expéditeur pour send_mail / EmailMessage.
    Si EMAIL_FROM_DISPLAY_NAME est défini : « Nom » <adresse@domaine>.
    """
    email = (getattr(settings, 'DEFAULT_FROM_EMAIL', None) or '').strip() or 'noreply@africahireplus.com'
    name = (getattr(settings, 'EMAIL_FROM_DISPLAY_NAME', None) or '').strip()
    if name:
        return formataddr((name, email))
    return email


def get_from_email_for_company(company: Company | None) -> str:
    """
    Expéditeur pour les e-mails liés à une entreprise.
    Si `company.email` est renseigné : « Nom entreprise » <email@entreprise>.
    Sinon : même comportement que `get_from_email()` (DEFAULT_FROM_EMAIL / EMAIL_FROM_DISPLAY_NAME).
    """
    if company is not None:
        addr = (getattr(company, 'email', None) or '').strip()
        if addr:
            name = (company.name or '').strip() or 'Recrutement'
            return formataddr((name, addr))
    return get_from_email()
