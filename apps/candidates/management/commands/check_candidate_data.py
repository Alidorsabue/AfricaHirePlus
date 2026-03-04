"""
Vérifie en base que les données candidat (formation, expérience, langues, références) existent.
Usage:
  python manage.py check_candidate_data --company=1
  python manage.py check_candidate_data --job-slug=jd-programme-officer-cash-noa-kinshasa-131110
  python manage.py check_candidate_data --company=1 --job-slug=jd-programme-officer-cash-noa-kinshasa-131110
"""
import json
from django.core.management.base import BaseCommand

from apps.candidates.models import Candidate
from apps.applications.models import Application
from apps.jobs.models import JobOffer


def summarize_candidate(candidate: Candidate, prefix: str = "  ") -> None:
    """Affiche un résumé des champs JSON du candidat."""
    edu = candidate.education if hasattr(candidate, "education") else []
    exp = candidate.experience if hasattr(candidate, "experience") else []
    lang = candidate.languages if hasattr(candidate, "languages") else []
    refs = candidate.references if hasattr(candidate, "references") else []
    is_list = lambda x: isinstance(x, list)
    edu_ok = is_list(edu) and len(edu) > 0
    exp_ok = is_list(exp) and len(exp) > 0
    lang_ok = is_list(lang) and len(lang) > 0
    refs_ok = is_list(refs) and len(refs) > 0

    print(f"{prefix}email: {candidate.email}")
    print(f"{prefix}user_id: {candidate.user_id} (lié au compte: {'Oui' if candidate.user_id else 'NON'})")
    print(f"{prefix}education: {'OUI' if edu_ok else 'VIDE'} (type={type(edu).__name__}, len={len(edu) if is_list(edu) else 'N/A'})")
    if edu_ok:
        print(f"{prefix}  -> premier enregistrement: {json.dumps(edu[0], ensure_ascii=False, default=str)[:200]}...")
    print(f"{prefix}experience: {'OUI' if exp_ok else 'VIDE'} (type={type(exp).__name__}, len={len(exp) if is_list(exp) else 'N/A'})")
    if exp_ok:
        print(f"{prefix}  -> premier enregistrement: {json.dumps(exp[0], ensure_ascii=False, default=str)[:200]}...")
    print(f"{prefix}languages: {'OUI' if lang_ok else 'VIDE'} (len={len(lang) if is_list(lang) else 'N/A'})")
    print(f"{prefix}references: {'OUI' if refs_ok else 'VIDE'} (len={len(refs) if is_list(refs) else 'N/A'})")


class Command(BaseCommand):
    help = "Vérifie la présence des données candidat (formation, expérience, etc.) en base."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=int,
            help="ID de l'entreprise (affiche tous les candidats de cette entreprise)",
        )
        parser.add_argument(
            "--job-slug",
            type=str,
            help="Slug de l'offre (affiche les candidatures pour cette offre et les données des candidats)",
        )

    def handle(self, *args, **options):
        company_id = options.get("company")
        job_slug = options.get("job_slug")

        if not company_id and not job_slug:
            self.stdout.write("Indiquez --company=ID et/ou --job-slug=SLUG.")
            return

        if job_slug:
            job = JobOffer.objects.filter(slug=job_slug).select_related("company").first()
            if not job:
                self.stdout.write(self.style.ERROR(f"Offre avec slug '{job_slug}' introuvable."))
                return
            self.stdout.write(f"\n=== Offre: {job.title} (slug={job.slug}, company_id={job.company_id}) ===\n")
            apps = Application.objects.filter(job_offer=job).select_related("candidate", "candidate__user")
            if not apps.exists():
                self.stdout.write("Aucune candidature pour cette offre.")
            for app in apps:
                c = app.candidate
                self.stdout.write(f"\n--- Candidature #{app.id} (candidat_id={c.id}, applied_at={app.applied_at}) ---")
                summarize_candidate(c)
            return

        if company_id:
            candidates = Candidate.objects.filter(company_id=company_id).order_by("-updated_at")
            if not candidates.exists():
                self.stdout.write(self.style.WARNING(f"Aucun candidat pour company_id={company_id}."))
                return
            self.stdout.write(f"\n=== Candidats pour company_id={company_id} (total: {candidates.count()}) ===\n")
            for c in candidates:
                self.stdout.write(f"\n--- Candidat id={c.id} ({c.first_name} {c.last_name}) ---")
                summarize_candidate(c)
