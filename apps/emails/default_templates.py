"""
Templates d'email par défaut (sujet + corps HTML) pour chaque type.

Variables disponibles selon le type :
  - Tous : {{ candidate_name }}, {{ candidate_email }}, {{ job_title }},
           {{ company_name }}
  - Test : {{ test_title }}, {{ test_link }} (lien complet)
  - Corrector : {{ corrector_link }}, {{ test_title }}, {{ scope_str }},
                {{ expires_str }}, {{ recruiter_name }}

NB : le corps HTML est rendu DANS le wrapper branded (`render_branded_html`).
Inutile d'y mettre des styles inline ou un <html><body> — on se contente d'un
fragment de paragraphes / listes / liens.
"""
from apps.emails.models import EmailTemplate

# Types pour lesquels l'app envoie des emails automatiquement à la création
# de l'entreprise (signal). Les autres sont créés à la demande.
TEMPLATE_TYPES_USED_BY_APP = [
    EmailTemplate.TemplateType.APPLICATION_RECEIVED,
    EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION,
    EmailTemplate.TemplateType.APPLICATION_REJECTED,
    EmailTemplate.TemplateType.TEST_INVITATION,
    EmailTemplate.TemplateType.TEST_SUBMITTED,
    EmailTemplate.TemplateType.TEST_EXPIRED,
    EmailTemplate.TemplateType.CORRECTOR_INVITATION,
    EmailTemplate.TemplateType.CORRECTOR_REVOKED,
]

DEFAULT_TEMPLATES = {
    EmailTemplate.TemplateType.APPLICATION_RECEIVED: {
        'name': 'Confirmation de réception de candidature',
        'subject': 'Nous avons bien reçu votre candidature – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Nous accusons réception de votre candidature pour le poste <strong>{{ job_title }}</strong> au sein de {{ company_name }}.</p>
<p>Votre dossier va être étudié par notre équipe. Nous vous recontacterons si votre profil correspond à nos critères.</p>
<p>Cordialement,<br/>L'équipe RH de {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Nous avons bien reçu votre candidature pour le poste {{ job_title }} au sein de {{ company_name }}. Nous vous recontacterons si votre profil correspond à nos critères. Cordialement, L\'équipe RH de {{ company_name }}',
    },
    EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION: {
        'name': 'Notification shortlist',
        'subject': 'Votre candidature a été présélectionnée – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Bonne nouvelle : votre candidature pour le poste de <strong>{{ job_title }}</strong> au sein de {{ company_name }} a été retenue pour la suite du processus.</p>
<p>Nous vous contacterons prochainement pour les prochaines étapes (entretien, test, etc.).</p>
<p>Cordialement,<br/>L'équipe RH de {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Votre candidature pour le poste {{ job_title }} a été présélectionnée. Nous vous contacterons pour les prochaines étapes. Cordialement, L\'équipe RH de {{ company_name }}',
    },
    EmailTemplate.TemplateType.APPLICATION_REJECTED: {
        'name': 'Candidature non retenue',
        'subject': 'Suite à votre candidature – {{ job_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Suite à l'étude de votre candidature pour le poste <strong>{{ job_title }}</strong> au sein de {{ company_name }}, nous sommes au regret de vous informer que nous ne retenons pas votre profil pour cette offre.</p>
<p>Nous vous remercions pour l'intérêt que vous avez porté à notre entreprise et vous souhaitons beaucoup de succès dans vos démarches.</p>
<p>Cordialement,<br/>L'équipe RH de {{ company_name }}</p>''',
        'body_text': 'Bonjour {{ candidate_name }}, Suite à l\'étude de votre candidature pour le poste {{ job_title }}, nous ne retenons pas votre profil pour cette offre. Nous vous remercions et vous souhaitons succès dans vos démarches. Cordialement, L\'équipe RH de {{ company_name }}',
    },
    EmailTemplate.TemplateType.TEST_INVITATION: {
        'name': "Invitation à passer un test technique",
        'subject': '[{{ company_name }}] Test technique : {{ test_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Dans le cadre de votre candidature pour le poste de <strong>{{ job_title }}</strong> au sein de {{ company_name }}, nous vous invitons à passer le test technique <strong>{{ test_title }}</strong>.</p>
<p>Cliquez sur le bouton ci-dessous pour démarrer le test. Le lien est <strong>personnel</strong> et ne doit pas être partagé.</p>
<p style="font-size:13px;color:#64748b;">Conseils :<br/>
- Prévoyez un environnement calme et une connexion internet stable.<br/>
- Une fois le test démarré, le chronomètre court : ne fermez pas votre navigateur.<br/>
- Toutes vos réponses sont enregistrées automatiquement.</p>
<p>Bonne chance,<br/>L'équipe {{ company_name }}</p>''',
        'body_text': '',  # déduit du HTML
    },
    EmailTemplate.TemplateType.TEST_SUBMITTED: {
        'name': 'Test soumis par un candidat',
        'subject': '[{{ company_name }}] Test soumis : {{ candidate_name }}',
        'body_html': '''<p>Bonjour,</p>
<p>Le candidat <strong>{{ candidate_name }}</strong> ({{ candidate_email }}) vient de soumettre le test <strong>{{ test_title }}</strong>.</p>
<ul>
  <li>Score : <strong>{{ score_str }}</strong>{{ verdict }}</li>
  <li>Points en attente de révision manuelle : {{ pending_str }}</li>
  <li>Changements d'onglet : {{ tab_switch_count }} ({{ flagged_str }})</li>
</ul>
<p>Connectez-vous au tableau de bord pour consulter le rapport détaillé et l'éventuelle correction manuelle.</p>''',
        'body_text': '',
    },
    EmailTemplate.TemplateType.TEST_EXPIRED: {
        'name': 'Session de test expirée',
        'subject': '[{{ company_name }}] Test expiré : {{ test_title }}',
        'body_html': '''<p>Bonjour {{ candidate_name }},</p>
<p>Votre session du test <strong>{{ test_title }}</strong> a expiré car la durée impartie ({{ duration_minutes }} min) s'est écoulée sans soumission finale.</p>
<p>Si vous pensez qu'il s'agit d'une erreur, contactez directement le recruteur de {{ company_name }}.</p>
<p>Cordialement,<br/>L'équipe {{ company_name }}</p>''',
        'body_text': '',
    },
    EmailTemplate.TemplateType.CORRECTOR_INVITATION: {
        'name': 'Invitation correcteur externe',
        'subject': "[{{ company_name }}] Invitation à corriger un test technique",
        'body_html': '''<p>Bonjour {{ recipient_name }},</p>
<p>{{ recruiter_name_clause }}<strong>{{ company_name }}</strong> vous désigne comme correcteur(trice) externe pour le test technique suivant :</p>
<ul>
  <li><strong>Test :</strong> {{ test_title }}</li>
  <li><strong>Poste / rôle :</strong> {{ job_title }}</li>
  <li><strong>Périmètre :</strong> {{ scope_str }}</li>
  <li><strong>Expiration du lien :</strong> {{ expires_str }}</li>
</ul>
<p>Cliquez sur le bouton ci-dessous pour accéder directement à l'interface de correction. <strong>Aucun compte à créer</strong> — le lien est suffisant.</p>
<p style="font-size:13px;color:#64748b;"><strong>Important :</strong><br/>
- Les soumissions vous sont présentées de manière <strong>anonymisée</strong> (un code unique par candidat — pas de nom ni email).<br/>
- Ne partagez pas ce lien : il est strictement personnel.<br/>
- Vous pouvez modifier la note de TOUTES les questions, y compris celles déjà notées automatiquement.</p>
<p>Merci pour votre contribution.<br/>L'équipe {{ company_name }}</p>''',
        'body_text': '',
    },
    EmailTemplate.TemplateType.CORRECTOR_REVOKED: {
        'name': 'Accès correcteur révoqué',
        'subject': '[{{ company_name }}] Votre accès correcteur a été révoqué',
        'body_html': '''<p>Bonjour,</p>
<p>Votre accès en tant que correcteur(trice) pour le test <strong>{{ test_title }}</strong> de {{ company_name }} a été révoqué et n'est plus valide.</p>
<p>Si vous pensez qu'il s'agit d'une erreur, veuillez contacter directement le recruteur de {{ company_name }}.</p>
<p>Cordialement,</p>''',
        'body_text': '',
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
