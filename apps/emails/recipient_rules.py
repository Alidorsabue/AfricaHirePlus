"""
Règles destinataires par type de template : type → statuts de candidature concernés.
Utilisé pour l'endpoint recipients et l'affichage "Envoyé à".
"""
from apps.applications.models import Application

# type de template → liste de statuts Application.Status
TEMPLATE_TYPE_TO_STATUSES = {
    'application_received': [Application.Status.APPLIED],
    'application_rejected': [
        Application.Status.REJECTED,
        Application.Status.REJECTED_PRESELECTION,
        Application.Status.REJECTED_SELECTION,
        Application.Status.PRESELECTED,  # présélectionnés non shortlistés
    ],
    'shortlist_notification': [Application.Status.SHORTLISTED],
    'interview_invitation': [Application.Status.INTERVIEW],
    'offer_letter': [Application.Status.OFFER],
    'test_invitation': [Application.Status.SHORTLISTED],
    'reminder': [
        Application.Status.SHORTLISTED,
        Application.Status.PRESELECTED,
        Application.Status.INTERVIEW,
    ],
    'custom': list(Application.Status),
}

def get_recipient_statuses_for_type(template_type: str) -> list:
    """Retourne la liste des statuts de candidature pour un type de template."""
    return TEMPLATE_TYPE_TO_STATUSES.get(template_type, [])
