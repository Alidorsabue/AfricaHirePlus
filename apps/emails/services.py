"""
Service d'envoi d'emails transactionnels (P9 refactor) :

  * Tous les envois passent par `dispatch_email()` → audit log + HTML branded +
    backend pluggable (Brevo API / SMTP / console).
  * Les corps libres (TEST/CORRECTOR/...) sont injectés dans un template DB
    si présent, sinon un fallback hardcodé est utilisé.
  * Les liens sont des boutons CTA cliquables (et non plus du texte brut),
    ce qui réduit drastiquement le taux d'erreur de copier-coller pour les
    candidats et correcteurs.

API publique :
  - send_application_received / send_shortlist_notification / send_rejection_notification
  - send_test_invitation / send_test_submitted_notification / send_test_expired_notification
  - send_corrector_invitation / send_corrector_revocation
"""
from __future__ import annotations

import logging
from typing import Mapping, Optional

from django.conf import settings
from django.template import Context, Template

from apps.companies.models import Company
from apps.emails.models import EmailLog, EmailTemplate

from .dispatch import dispatch_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------
def _render_template(html_content: str, context: Mapping) -> str:
    """Rend un template Django avec un dict de contexte. Best-effort."""
    try:
        return Template(html_content or '').render(Context(dict(context)))
    except Exception as e:
        logger.warning('Template render failed: %s', e)
        return html_content or ''


def _get_template(company: Company, template_type: str) -> Optional[EmailTemplate]:
    """Template DB actif pour (company, type), ou None."""
    if not company:
        return None
    return EmailTemplate.objects.filter(
        company=company, template_type=template_type, is_active=True,
    ).first()


def _render_db_or_fallback(
    company: Company,
    template_type: str,
    *,
    fallback_subject: str,
    fallback_body_html: str,
    context: Mapping,
) -> tuple[str, str]:
    """
    Si un template DB actif existe, on l'utilise. Sinon, on prend le
    fallback hardcodé. Le résultat est TOUJOURS un fragment HTML (pas un
    document complet) — le wrapper `render_branded_html` l'enveloppe ensuite.
    """
    tpl = _get_template(company, template_type)
    if tpl:
        subject = _render_template(tpl.subject, context)
        body_html = _render_template(tpl.body_html, context)
        return subject, body_html
    return (
        _render_template(fallback_subject, context),
        _render_template(fallback_body_html, context),
    )


def _build_corrector_link(token: str) -> str:
    """
    Construit le lien magique vers l'interface correcteur.

    Configurable via les settings `FRONTEND_BASE_URL` (URL absolue du front)
    et `CORRECTOR_LINK_PATH` (chemin React, défaut `/correct`).
    """
    base = (getattr(settings, 'FRONTEND_BASE_URL', '') or '').rstrip('/')
    path = getattr(settings, 'CORRECTOR_LINK_PATH', '/correct')
    if not base:
        return f'{path}?token={token}'
    return f'{base}{path}?token={token}'


def _build_test_link(grant) -> str:
    """Lien direct pour lancer un test à partir d'un TestAccessGrant."""
    base = (getattr(settings, 'FRONTEND_BASE_URL', '') or '').rstrip('/')
    path = getattr(settings, 'TEST_ACCESS_PATH', '/candidat/tests/access')
    code = getattr(grant.test, 'access_code', '') or ''
    qs = f'?token={grant.token}'
    if code:
        qs += f'&code={code}&test_id={grant.test_id}'
    return f'{base}{path}{qs}' if base else f'{path}{qs}'


# ---------------------------------------------------------------------------
# Emails liés à la candidature
# ---------------------------------------------------------------------------
def send_application_received(
    company: Company,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
) -> Optional[EmailLog]:
    """Confirmation de réception de candidature (best-effort)."""
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject, body = _render_db_or_fallback(
        company, EmailTemplate.TemplateType.APPLICATION_RECEIVED,
        fallback_subject='Nous avons bien reçu votre candidature – {{ job_title }}',
        fallback_body_html=(
            '<p>Bonjour {{ candidate_name }},</p>'
            '<p>Nous accusons réception de votre candidature pour le poste '
            '<strong>{{ job_title }}</strong> au sein de {{ company_name }}.</p>'
            '<p>Votre dossier va être étudié par notre équipe. Nous vous '
            'recontacterons si votre profil correspond à nos critères.</p>'
            '<p>Cordialement,<br/>L\'équipe RH de {{ company_name }}</p>'
        ),
        context=ctx,
    )
    return dispatch_email(
        company=company,
        template_type=EmailTemplate.TemplateType.APPLICATION_RECEIVED,
        recipient=candidate_email,
        subject=subject,
        body_html=body,
        preheader='Confirmation de votre candidature',
        footer_note='Vous recevez cet email suite à votre candidature.',
        tags=['application', 'received'],
    )


def send_shortlist_notification(
    company: Company,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
) -> Optional[EmailLog]:
    """Notification : candidat shortlisté."""
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject, body = _render_db_or_fallback(
        company, EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION,
        fallback_subject='Votre candidature a été présélectionnée – {{ job_title }}',
        fallback_body_html=(
            '<p>Bonjour {{ candidate_name }},</p>'
            '<p>Bonne nouvelle : votre candidature pour le poste de '
            '<strong>{{ job_title }}</strong> au sein de {{ company_name }} '
            'a été retenue pour la suite du processus.</p>'
            '<p>Nous vous contacterons prochainement pour les prochaines étapes '
            '(entretien, test, etc.).</p>'
            '<p>Cordialement,<br/>L\'équipe RH de {{ company_name }}</p>'
        ),
        context=ctx,
    )
    return dispatch_email(
        company=company,
        template_type=EmailTemplate.TemplateType.SHORTLIST_NOTIFICATION,
        recipient=candidate_email,
        subject=subject,
        body_html=body,
        preheader='Vous êtes shortlisté(e)',
        footer_note='Vous recevez cet email suite à votre candidature.',
        tags=['application', 'shortlist'],
    )


def send_rejection_notification(
    company: Company,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
) -> Optional[EmailLog]:
    """Notification : candidature rejetée."""
    ctx = {
        'candidate_name': candidate_name,
        'candidate_email': candidate_email,
        'job_title': job_title,
        'company_name': company.name,
    }
    subject, body = _render_db_or_fallback(
        company, EmailTemplate.TemplateType.APPLICATION_REJECTED,
        fallback_subject='Suite à votre candidature – {{ job_title }}',
        fallback_body_html=(
            '<p>Bonjour {{ candidate_name }},</p>'
            '<p>Suite à l\'étude de votre candidature pour le poste '
            '<strong>{{ job_title }}</strong> au sein de {{ company_name }}, '
            'nous sommes au regret de vous informer que nous ne retenons pas '
            'votre profil pour cette offre.</p>'
            '<p>Nous vous remercions pour l\'intérêt que vous avez porté à '
            'notre entreprise et vous souhaitons beaucoup de succès dans vos '
            'démarches.</p>'
            '<p>Cordialement,<br/>L\'équipe RH de {{ company_name }}</p>'
        ),
        context=ctx,
    )
    return dispatch_email(
        company=company,
        template_type=EmailTemplate.TemplateType.APPLICATION_REJECTED,
        recipient=candidate_email,
        subject=subject,
        body_html=body,
        preheader='Décision relative à votre candidature',
        footer_note='Vous recevez cet email suite à votre candidature.',
        tags=['application', 'rejected'],
    )


# ---------------------------------------------------------------------------
# Emails liés aux tests techniques (apps.tests)
# ---------------------------------------------------------------------------
def send_test_invitation(grant) -> Optional[EmailLog]:
    """
    Email d'invitation à passer un test (avec token d'accès unique P5).

    `grant` : `apps.tests.models.TestAccessGrant`.
    """
    try:
        application = grant.application
        candidate = application.candidate
        company = application.job_offer.company
        link = _build_test_link(grant)
        ctx = {
            'candidate_name': candidate.get_full_name(),
            'candidate_email': candidate.email,
            'job_title': application.job_offer.title,
            'company_name': company.name,
            'test_title': grant.test.title,
            'test_link': link,
        }
        subject, body = _render_db_or_fallback(
            company, EmailTemplate.TemplateType.TEST_INVITATION,
            fallback_subject='[{{ company_name }}] Test technique : {{ test_title }}',
            fallback_body_html=(
                '<p>Bonjour {{ candidate_name }},</p>'
                '<p>Vous êtes invité(e) à passer le test '
                '<strong>{{ test_title }}</strong> dans le cadre de votre '
                'candidature pour le poste de <strong>{{ job_title }}</strong>.</p>'
                '<p>Cliquez sur le bouton ci-dessous pour démarrer. Le lien est '
                '<strong>personnel</strong>, ne le partagez pas.</p>'
                '<p>Bonne chance,<br/>L\'équipe {{ company_name }}</p>'
            ),
            context=ctx,
        )
        return dispatch_email(
            company=company,
            template_type=EmailTemplate.TemplateType.TEST_INVITATION,
            recipient=candidate.email,
            subject=subject,
            body_html=body,
            cta_label='Démarrer le test',
            cta_url=link,
            preheader=f'Test technique : {grant.test.title}',
            footer_note=(
                "Ce lien est strictement personnel. Ne le partagez pas. "
                "Pour toute question, contactez directement le recruteur."
            ),
            tags=['test', 'invitation'],
            related_application_id=application.id,
            related_object=grant,
        )
    except Exception as e:
        logger.warning('send_test_invitation a échoué : %s', e)
        return None


def send_test_submitted_notification(result) -> Optional[EmailLog]:
    """
    Email au recruteur quand un candidat soumet un test.
    `result` : `apps.tests.models.CandidateTestResult`.
    """
    try:
        application = result.application
        candidate = application.candidate
        company = application.job_offer.company
        recruiter_email = getattr(application.job_offer.created_by, 'email', None)
        if not recruiter_email:
            recruiter_email = company.email
        if not recruiter_email:
            return None

        score_str = (
            f'{float(result.score or 0):.2f} / {float(result.max_score or 0):.2f}'
        )
        pending = float(result.pending_review_points or 0)
        pending_str = f'{pending:.2f}' if pending else '0'
        verdict = ''
        if result.is_passed is True:
            verdict = ' — RÉUSSI'
        elif result.is_passed is False:
            verdict = ' — ÉCHEC'
        flagged_str = 'suspect' if result.is_flagged else 'normal'

        ctx = {
            'candidate_name': candidate.get_full_name(),
            'candidate_email': candidate.email,
            'job_title': application.job_offer.title,
            'company_name': company.name,
            'test_title': result.test.title,
            'score_str': score_str,
            'pending_str': pending_str,
            'verdict': verdict,
            'tab_switch_count': result.tab_switch_count,
            'flagged_str': flagged_str,
        }
        subject, body = _render_db_or_fallback(
            company, EmailTemplate.TemplateType.TEST_SUBMITTED,
            fallback_subject='[{{ company_name }}] Test soumis : {{ candidate_name }}',
            fallback_body_html=(
                '<p>Bonjour,</p>'
                '<p>Le candidat <strong>{{ candidate_name }}</strong> '
                '({{ candidate_email }}) vient de soumettre le test '
                '<strong>{{ test_title }}</strong>.</p>'
                '<ul>'
                '<li>Score : <strong>{{ score_str }}</strong>{{ verdict }}</li>'
                '<li>Points en attente de révision : {{ pending_str }}</li>'
                '<li>Changements d\'onglet : {{ tab_switch_count }} ({{ flagged_str }})</li>'
                '</ul>'
                '<p>Consultez le tableau de bord pour le rapport détaillé.</p>'
            ),
            context=ctx,
        )
        return dispatch_email(
            company=company,
            template_type=EmailTemplate.TemplateType.TEST_SUBMITTED,
            recipient=recruiter_email,
            subject=subject,
            body_html=body,
            preheader=f'{candidate.get_full_name()} a soumis le test',
            footer_note='Notification automatique du module tests.',
            tags=['test', 'submitted'],
            related_application_id=application.id,
            related_object=result,
        )
    except Exception as e:
        logger.warning('send_test_submitted_notification a échoué : %s', e)
        return None


def send_test_expired_notification(result) -> Optional[EmailLog]:
    """Email au candidat quand sa session de test expire automatiquement."""
    try:
        application = result.application
        candidate = application.candidate
        company = application.job_offer.company
        ctx = {
            'candidate_name': candidate.get_full_name(),
            'candidate_email': candidate.email,
            'company_name': company.name,
            'test_title': result.test.title,
            'duration_minutes': result.test.duration_minutes or 0,
        }
        subject, body = _render_db_or_fallback(
            company, EmailTemplate.TemplateType.TEST_EXPIRED,
            fallback_subject='[{{ company_name }}] Test expiré : {{ test_title }}',
            fallback_body_html=(
                '<p>Bonjour {{ candidate_name }},</p>'
                '<p>Votre session du test <strong>{{ test_title }}</strong> a '
                'expiré car la durée impartie ({{ duration_minutes }} min) '
                's\'est écoulée sans soumission finale.</p>'
                '<p>Si vous pensez qu\'il s\'agit d\'une erreur, contactez le '
                'recruteur de {{ company_name }}.</p>'
                '<p>Cordialement,</p>'
            ),
            context=ctx,
        )
        return dispatch_email(
            company=company,
            template_type=EmailTemplate.TemplateType.TEST_EXPIRED,
            recipient=candidate.email,
            subject=subject,
            body_html=body,
            preheader='Votre session de test a expiré',
            footer_note='Notification automatique du module tests.',
            tags=['test', 'expired'],
            related_application_id=application.id,
            related_object=result,
        )
    except Exception as e:
        logger.warning('send_test_expired_notification a échoué : %s', e)
        return None


# ---------------------------------------------------------------------------
# Emails correcteur externe (P8)
# ---------------------------------------------------------------------------
def send_corrector_invitation(assignment) -> Optional[EmailLog]:
    """
    Email d'invitation à un correcteur externe.

    `assignment` : `apps.tests.models.CorrectorAssignment`.
    """
    try:
        test = assignment.test
        company = assignment.company
        job_title = test.job_offer.title if test.job_offer_id else ''
        recipient_name = assignment.full_name or (assignment.email.split('@')[0] if assignment.email else '')
        assigned_count = (
            assignment.assigned_applications.count()
            if not assignment.all_candidates else None
        )
        scope_str = (
            'Tous les candidats ayant soumis ce test (y compris les futures soumissions).'
            if assignment.all_candidates else
            f'{assigned_count} candidat(s) spécifiquement sélectionné(s) par le recruteur.'
        )
        expires_str = (
            assignment.expires_at.strftime('%d/%m/%Y à %H:%M')
            if assignment.expires_at else 'aucune (lien sans expiration)'
        )
        recruiter_name = ''
        if assignment.assigned_by:
            try:
                recruiter_name = (
                    assignment.assigned_by.get_full_name() or assignment.assigned_by.email
                )
            except Exception:
                recruiter_name = getattr(assignment.assigned_by, 'email', '')
        recruiter_clause = f'{recruiter_name} de ' if recruiter_name else ''

        link = _build_corrector_link(assignment.token)

        ctx = {
            'recipient_name': recipient_name,
            'recruiter_name': recruiter_name,
            'recruiter_name_clause': recruiter_clause,
            'company_name': company.name,
            'test_title': test.title,
            'job_title': job_title,
            'scope_str': scope_str,
            'expires_str': expires_str,
            'corrector_link': link,
        }
        subject, body = _render_db_or_fallback(
            company, EmailTemplate.TemplateType.CORRECTOR_INVITATION,
            fallback_subject="[{{ company_name }}] Invitation à corriger un test technique",
            fallback_body_html=(
                '<p>Bonjour {{ recipient_name }},</p>'
                '<p>{{ recruiter_name_clause }}<strong>{{ company_name }}</strong> '
                'vous désigne comme correcteur(trice) externe pour le test :</p>'
                '<ul>'
                '<li><strong>Test :</strong> {{ test_title }}</li>'
                '<li><strong>Poste / rôle :</strong> {{ job_title }}</li>'
                '<li><strong>Périmètre :</strong> {{ scope_str }}</li>'
                '<li><strong>Expiration du lien :</strong> {{ expires_str }}</li>'
                '</ul>'
                '<p>Cliquez sur le bouton ci-dessous pour accéder à l\'interface '
                'de correction. <strong>Aucun compte à créer.</strong></p>'
                '<p style="font-size:13px;color:#64748b;">'
                'Les soumissions sont anonymisées (vous ne voyez ni nom ni email). '
                'Vous pouvez modifier toutes les notes, y compris les corrections '
                'automatiques.</p>'
                '<p>Merci pour votre contribution,<br/>L\'équipe {{ company_name }}</p>'
            ),
            context=ctx,
        )
        return dispatch_email(
            company=company,
            template_type=EmailTemplate.TemplateType.CORRECTOR_INVITATION,
            recipient=assignment.email,
            subject=subject,
            body_html=body,
            cta_label='Accéder à la correction',
            cta_url=link,
            preheader=f'Correction du test : {test.title}',
            footer_note=(
                "Ce lien est strictement personnel — ne le partagez pas. "
                "Pour toute question, contactez le recruteur."
            ),
            tags=['corrector', 'invitation'],
            related_object=assignment,
        )
    except Exception as e:
        logger.warning('send_corrector_invitation a échoué : %s', e)
        return None


def send_corrector_revocation(assignment) -> Optional[EmailLog]:
    """Notifie le correcteur que son accès a été révoqué."""
    try:
        company = assignment.company
        ctx = {
            'company_name': company.name,
            'test_title': assignment.test.title,
        }
        subject, body = _render_db_or_fallback(
            company, EmailTemplate.TemplateType.CORRECTOR_REVOKED,
            fallback_subject='[{{ company_name }}] Votre accès correcteur a été révoqué',
            fallback_body_html=(
                '<p>Bonjour,</p>'
                '<p>Votre accès en tant que correcteur(trice) pour le test '
                '<strong>{{ test_title }}</strong> de {{ company_name }} a été '
                'révoqué et n\'est plus valide.</p>'
                '<p>Si vous pensez qu\'il s\'agit d\'une erreur, contactez '
                'directement le recruteur de {{ company_name }}.</p>'
                '<p>Cordialement,</p>'
            ),
            context=ctx,
        )
        return dispatch_email(
            company=company,
            template_type=EmailTemplate.TemplateType.CORRECTOR_REVOKED,
            recipient=assignment.email,
            subject=subject,
            body_html=body,
            preheader='Votre accès correcteur a été révoqué',
            footer_note='Notification automatique du module correcteur.',
            tags=['corrector', 'revoked'],
            related_object=assignment,
        )
    except Exception as e:
        logger.warning('send_corrector_revocation a échoué : %s', e)
        return None
