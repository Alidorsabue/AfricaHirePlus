"""
Services métier candidatures : soumission, détection doublon, get_or_create candidat, workflow (screening + emails), manual override.
"""
import logging

from django.utils import timezone

from apps.applications.models import Application
from apps.candidates.models import Candidate
from apps.jobs.models import JobOffer
from apps.jobs.services import compute_preselection, compute_screening_score, run_auto_preselection
from apps.emails.services import send_application_received, send_shortlist_notification
from apps.core.cv_extraction import extract_text_from_uploaded_file

logger = logging.getLogger(__name__)

# Seuil de score pour présélection automatique (si score >= 60 → statut PRESELECTED)
SCREENING_THRESHOLD = 60.0


def apply_manual_override(
    application: Application,
    action: str,
    *,
    reason: str = '',
    new_status: str | None = None,
    new_score: float | None = None,
) -> Application:
    """
    Applique un ajustement manuel sur une candidature.
    Actions : ADD_TO_SHORTLIST, REMOVE_FROM_SHORTLIST, FORCE_STATUS, UPDATE_SCORE.
    Marque is_manually_adjusted = True pour ne plus recalculer ce candidat.
    """
    application.is_manually_adjusted = True
    application.manual_override_reason = reason or application.manual_override_reason or ''
    update_fields = ['is_manually_adjusted', 'manual_override_reason', 'updated_at']

    if action == 'ADD_TO_SHORTLIST':
        application.manually_added_to_shortlist = True
        application.status = Application.Status.SHORTLISTED
        update_fields.extend(['manually_added_to_shortlist', 'status'])
    elif action == 'REMOVE_FROM_SHORTLIST':
        application.manually_added_to_shortlist = False
        application.status = Application.Status.REJECTED_SELECTION
        update_fields.extend(['manually_added_to_shortlist', 'status'])
    elif action == 'FORCE_STATUS' and new_status:
        application.status = new_status
        update_fields.append('status')
    elif action == 'UPDATE_SCORE' and new_score is not None:
        application.selection_score = float(new_score)
        update_fields.append('selection_score')

    application.save(update_fields=update_fields)
    return application


def check_duplicate_application(job_offer_id: int, candidate_email: str, company_id: int) -> bool:
    """Retourne True si une candidature existe déjà pour cette offre et cet email (même candidat)."""
    return Application.objects.filter(
        job_offer_id=job_offer_id,
        candidate__company_id=company_id,
        candidate__email__iexact=candidate_email,
    ).exists()


def get_existing_application(job_offer_id: int, candidate_email: str, company_id: int) -> Application | None:
    """Retourne la candidature existante pour cette offre et cet email, ou None."""
    return Application.objects.filter(
        job_offer_id=job_offer_id,
        candidate__company_id=company_id,
        candidate__email__iexact=candidate_email,
    ).select_related('candidate', 'job_offer').first()


def job_accepts_applications(job_offer: JobOffer) -> bool:
    """Retourne True si l'offre est encore ouverte (publiée, date limite non dépassée)."""
    if job_offer.status != JobOffer.Status.PUBLISHED:
        return False
    if job_offer.deadline:
        return timezone.now() <= job_offer.deadline
    return True


def get_or_create_candidate(
    company_id: int,
    email: str,
    first_name: str,
    last_name: str,
    phone: str = '',
    resume=None,
    linkedin_url: str = '',
    portfolio_url: str = '',
    summary: str = '',
    experience_years: int | None = None,
    education_level: str = '',
    current_position: str = '',
    location: str = '',
    country: str = '',
    skills: list | None = None,
    raw_cv_text: str = '',
    user=None,
    education: list | None = None,
    experience: list | None = None,
    languages: list | None = None,
    references: list | None = None,
    title: str = '',
    preferred_name: str = '',
    date_of_birth=None,
    gender: str = '',
    address: str = '',
    address_line2: str = '',
    city: str = '',
    postcode: str = '',
    cell_number: str = '',
    nationality: str = '',
    second_nationality: str = '',
) -> Candidate:
    """Récupère ou crée le candidat (unique company + email). Met à jour les champs fournis et lie user si fourni."""
    # Extraction du texte du CV (PDF/Word) en amont du scoring et de la recherche
    effective_raw_cv_text = raw_cv_text or ''
    if resume:
        extracted = extract_text_from_uploaded_file(resume)
        if extracted:
            effective_raw_cv_text = extracted
            logger.debug("cv_extraction: %d caractères extraits du CV pour candidat %s", len(extracted), email)

    candidate = Candidate.objects.filter(company_id=company_id, email__iexact=email).first()
    if candidate:
        # Mise à jour partielle des champs envoyés
        update_fields = []
        if first_name:
            candidate.first_name = first_name
            update_fields.append('first_name')
        if last_name:
            candidate.last_name = last_name
            update_fields.append('last_name')
        if phone is not None:
            candidate.phone = phone
            update_fields.append('phone')
        if resume:
            candidate.resume = resume
            update_fields.append('resume')
        if linkedin_url is not None:
            candidate.linkedin_url = linkedin_url
            update_fields.append('linkedin_url')
        if portfolio_url is not None:
            candidate.portfolio_url = portfolio_url
            update_fields.append('portfolio_url')
        if summary is not None:
            candidate.summary = summary
            update_fields.append('summary')
        if experience_years is not None:
            candidate.experience_years = experience_years
            update_fields.append('experience_years')
        if education_level is not None:
            candidate.education_level = education_level
            update_fields.append('education_level')
        if current_position is not None:
            candidate.current_position = current_position
            update_fields.append('current_position')
        if location is not None:
            candidate.location = location
            update_fields.append('location')
        if country is not None:
            candidate.country = country
            update_fields.append('country')
        if skills is not None:
            candidate.skills = skills
            update_fields.append('skills')
        if effective_raw_cv_text:
            candidate.raw_cv_text = effective_raw_cv_text
            update_fields.append('raw_cv_text')
        if user is not None:
            candidate.user = user
            update_fields.append('user')
        if education is not None:
            candidate.education = education
            update_fields.append('education')
        if experience is not None:
            candidate.experience = experience
            update_fields.append('experience')
        if languages is not None:
            candidate.languages = languages
            update_fields.append('languages')
        if references is not None:
            candidate.references = references
            update_fields.append('references')
        if title is not None:
            candidate.title = title or ''
            update_fields.append('title')
        if preferred_name is not None:
            candidate.preferred_name = preferred_name or ''
            update_fields.append('preferred_name')
        if date_of_birth is not None:
            candidate.date_of_birth = date_of_birth
            update_fields.append('date_of_birth')
        if gender is not None:
            candidate.gender = gender or ''
            update_fields.append('gender')
        if address is not None:
            candidate.address = address or ''
            update_fields.append('address')
        if address_line2 is not None:
            candidate.address_line2 = address_line2 or ''
            update_fields.append('address_line2')
        if city is not None:
            candidate.city = city or ''
            update_fields.append('city')
        if postcode is not None:
            candidate.postcode = postcode or ''
            update_fields.append('postcode')
        if cell_number is not None:
            candidate.cell_number = cell_number or ''
            update_fields.append('cell_number')
        if nationality is not None:
            candidate.nationality = nationality or ''
            update_fields.append('nationality')
        if second_nationality is not None:
            candidate.second_nationality = second_nationality or ''
            update_fields.append('second_nationality')
        if update_fields:
            candidate.save(update_fields=update_fields)
        return candidate

    # Nouveau candidat : création avec tous les champs
    return Candidate.objects.create(
        company_id=company_id,
        email=email,
        first_name=first_name or '',
        last_name=last_name or '',
        phone=phone or '',
        resume=resume,
        linkedin_url=linkedin_url or '',
        portfolio_url=portfolio_url or '',
        summary=summary or '',
        experience_years=experience_years,
        education_level=education_level or '',
        current_position=current_position or '',
        location=location or '',
        country=country or '',
        skills=skills or [],
        raw_cv_text=effective_raw_cv_text or '',
        user=user,
        education=education or [],
        experience=experience or [],
        languages=languages or [],
        references=references or [],
        title=title or '',
        preferred_name=preferred_name or '',
        date_of_birth=date_of_birth,
        gender=gender or '',
        address=address or '',
        address_line2=address_line2 or '',
        city=city or '',
        postcode=postcode or '',
        cell_number=cell_number or '',
        nationality=nationality or '',
        second_nationality=second_nationality or '',
    )


def submit_application(
    job_offer: JobOffer,
    email: str,
    first_name: str,
    last_name: str,
    cover_letter: str = '',
    source: str = 'public',
    phone: str = '',
    resume=None,
    linkedin_url: str = '',
    portfolio_url: str = '',
    summary: str = '',
    experience_years: int | None = None,
    education_level: str = '',
    current_position: str = '',
    location: str = '',
    country: str = '',
    skills: list | None = None,
    raw_cv_text: str = '',
    run_screening: bool = True,
    send_confirmation_email: bool = True,
    user=None,
    education: list | None = None,
    experience: list | None = None,
    languages: list | None = None,
    references: list | None = None,
    cover_letter_document=None,
    signature_text: str = '',
    title: str = '',
    preferred_name: str = '',
    date_of_birth=None,
    gender: str = '',
    address: str = '',
    address_line2: str = '',
    city: str = '',
    postcode: str = '',
    cell_number: str = '',
    nationality: str = '',
    second_nationality: str = '',
) -> tuple[Application, bool]:
    """
    Soumet ou met à jour une candidature.
    - Si l'offre est clôturée : erreur.
    - Si une candidature existe déjà pour cette offre et cet email, et que l'offre accepte encore les candidatures :
      met à jour le candidat et la candidature, relance le screening, retourne (application, True).
    - Sinon crée une nouvelle candidature et retourne (application, False).
    """
    from rest_framework.exceptions import ValidationError

    if job_offer.status == JobOffer.Status.CLOSED:
        raise ValidationError({'detail': 'Cette offre est clôturée. Les candidatures ne sont plus acceptées.'})
    company_id = job_offer.company_id
    existing = get_existing_application(job_offer.id, email, company_id)
    if existing:
        if not job_accepts_applications(job_offer):
            raise ValidationError({'detail': 'Une candidature existe déjà pour cette offre. L\'offre n\'accepte plus de mise à jour.'})
        # Mise à jour : candidat + candidature
        candidate = get_or_create_candidate(
            company_id=company_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            resume=resume,
            linkedin_url=linkedin_url,
            portfolio_url=portfolio_url,
            summary=summary,
            experience_years=experience_years,
            education_level=education_level,
            current_position=current_position,
            location=location,
            country=country,
            skills=skills,
            raw_cv_text=raw_cv_text,
            user=user,
            education=education,
            experience=experience,
            languages=languages,
            references=references,
            title=title,
            preferred_name=preferred_name,
            date_of_birth=date_of_birth,
            gender=gender,
            address=address,
            address_line2=address_line2,
            city=city,
            postcode=postcode,
            cell_number=cell_number,
            nationality=nationality,
            second_nationality=second_nationality,
        )
        signed_at = timezone.now() if signature_text else None
        existing.cover_letter = cover_letter or existing.cover_letter
        if cover_letter_document:
            existing.cover_letter_document = cover_letter_document
        existing.signature_text = signature_text or existing.signature_text
        existing.signed_at = signed_at or existing.signed_at
        existing.save(update_fields=['cover_letter', 'cover_letter_document', 'signature_text', 'signed_at', 'updated_at'])
        if run_screening:
            run_auto_preselection(existing)
            existing.refresh_from_db()
        return (existing, True)

    candidate = get_or_create_candidate(
        company_id=company_id,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        resume=resume,
        linkedin_url=linkedin_url,
        portfolio_url=portfolio_url,
        summary=summary,
        experience_years=experience_years,
        education_level=education_level,
        current_position=current_position,
        location=location,
        country=country,
        skills=skills,
        raw_cv_text=raw_cv_text,
        user=user,
        education=education,
        experience=experience,
        languages=languages,
        references=references,
        title=title,
        preferred_name=preferred_name,
        date_of_birth=date_of_birth,
        gender=gender,
        address=address,
        address_line2=address_line2,
        city=city,
        postcode=postcode,
        cell_number=cell_number,
        nationality=nationality,
        second_nationality=second_nationality,
    )

    signed_at = timezone.now() if signature_text else None
    # Création de la candidature (statut APPLIED)
    application = Application.objects.create(
        job_offer=job_offer,
        candidate=candidate,
        status=Application.Status.APPLIED,
        cover_letter=cover_letter,
        cover_letter_document=cover_letter_document,
        signature_text=signature_text,
        signed_at=signed_at,
        source=source,
    )

    # Présélection automatique : gérée par le signal post_save ; rafraîchir pour avoir le bon statut
    application.refresh_from_db()
    if run_screening and application.status == Application.Status.PRESELECTED and send_confirmation_email:
            try:
                send_shortlist_notification(
                    company=job_offer.company,
                    candidate_name=candidate.get_full_name(),
                    candidate_email=candidate.email,
                    job_title=job_offer.title,
                )
            except Exception as e:
                logger.warning('Shortlist email failed: %s', e)

    # Email de confirmation de réception de la candidature
    if send_confirmation_email:
        try:
            send_application_received(
                company=job_offer.company,
                candidate_name=candidate.get_full_name(),
                candidate_email=candidate.email,
                job_title=job_offer.title,
            )
        except Exception as e:
            logger.warning('Confirmation email failed: %s', e)

    return (application, False)
