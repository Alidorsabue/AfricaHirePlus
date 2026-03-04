"""
Templates d'email par défaut (sujet + corps HTML) pour chaque type.
Variables disponibles : {{ candidate_name }}, {{ candidate_email }}, {{ job_title }}, {{ company_name }}.
Utilisés à la création d'une entreprise (signal) ou par la commande create_default_email_templates.
"""
from apps.emails.models import EmailTemplate

# Types pour lesquels l'app envoie des emails automatiquement
TEMPLATE_TYPES_USED_BY_APP = [
    EmailTemplate.TemplateType.APPLICATION_RECEIVED,
    EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION,
    EmailTemplate.TemplateType.APPLICATION_REJECTED,
]

DEFAULT_TEMPLATES = {
    EmailTemplate.TemplateType.APPLICATION_RECEIVED: {
        'name': 'Confirmation de réception de candidature',
        'subject': 'Nous avons bien reçu votre candidature – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Nous accusons réception de votre candidature pour le poste <strong>{{ job_title }}</strong> au sein de {{ company_name }}.</p>
<p>Votre dossier va être étudié par notre équipe. Nous vous recontacterons si votre profil correspond à nos critères.</p>
<p>Cordialement,<br/>L'équipe {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Nous avons bien reçu votre candidature pour le poste {{ job_title }} au sein de {{ company_name }}. Nous vous recontacterons si votre profil correspond à nos critères. Cordialement, L\'équipe {{ company_name }}',
    },
    EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION: {
        'name': 'Notification shortlist',
        'subject': 'Votre candidature a été présélectionnée – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Bonne nouvelle : votre candidature pour le poste <strong>{{ job_title }}</strong> au sein de {{ company_name }} a été retenue pour la suite du processus.</p>
<p>Nous vous contacterons prochainement pour les prochaines étapes (entretien, test, etc.).</p>
<p>Cordialement,<br/>L'équipe {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Votre candidature pour le poste {{ job_title }} a été présélectionnée. Nous vous contacterons pour les prochaines étapes. Cordialement, L\'équipe {{ company_name }}',
    },
    EmailTemplate.TemplateType.APPLICATION_REJECTED: {
        'name': 'Candidature non retenue',
        'subject': 'Suite à votre candidature – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Suite à l'étude de votre candidature pour le poste <strong>{{ job_title }}</strong> au sein de {{ company_name }}, nous sommes au regret de vous informer que nous ne retenons pas votre profil pour cette offre.</p>
<p>Nous vous remercions pour l'intérêt que vous avez porté à notre entreprise et vous souhaitons beaucoup de succès dans vos démarches.</p>
<p>Cordialement,<br/>L'équipe {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Suite à l\'étude de votre candidature pour le poste {{ job_title }}, nous ne retenons pas votre profil pour cette offre. Nous vous remercions et vous souhaitons succès dans vos démarches. Cordialement, L\'équipe {{ company_name }}',
    },
}


def create_default_templates_for_company(company):
    """
    Crée les templates par défaut pour une entreprise (un par type utilisé par l'app).
    N'écrase pas un template existant pour (company, template_type).
    Retourne le nombre de templates créés.
    """
    from apps.emails.models import EmailTemplate

    created = 0
    for template_type in TEMPLATE_TYPES_USED_BY_APP:
        if EmailTemplate.objects.filter(company=company, template_type=template_type).exists():
            continue
        data = DEFAULT_TEMPLATES.get(template_type)
        if not data:
            continue
        EmailTemplate.objects.create(
            company=company,
            name=data['name'],
            template_type=template_type,
            subject=data['subject'],
            body_html=data.get('body_html', ''),
            body_text=data.get('body_text', ''),
            is_active=True,
        )
        created += 1
    return created
