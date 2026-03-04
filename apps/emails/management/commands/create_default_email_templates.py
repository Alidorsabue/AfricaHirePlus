"""
Crée les templates d'email par défaut (candidature reçue, shortlist, refus) pour une ou toutes les entreprises.
Les templates existants ne sont pas modifiés.
Usage:
  python manage.py create_default_email_templates --company=1
  python manage.py create_default_email_templates --all
"""
from django.core.management.base import BaseCommand

from apps.companies.models import Company
from apps.emails.default_templates import create_default_templates_for_company


class Command(BaseCommand):
    help = "Crée les templates d'email par défaut (candidature reçue, shortlist, refus) par entreprise."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company',
            type=int,
            help="ID de l'entreprise pour laquelle créer les templates manquants.",
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help="Créer les templates manquants pour toutes les entreprises actives.",
        )

    def handle(self, *args, **options):
        company_id = options.get('company')
        all_companies = options.get('all')

        if not company_id and not all_companies:
            self.stderr.write(
                self.style.ERROR('Indiquez --company=ID ou --all.')
            )
            return

        if company_id and all_companies:
            self.stderr.write(
                self.style.ERROR('Utilisez soit --company=ID soit --all, pas les deux.')
            )
            return

        if company_id:
            company = Company.objects.filter(pk=company_id).first()
            if not company:
                self.stderr.write(self.style.ERROR(f'Entreprise avec id={company_id} introuvable.'))
                return
            companies = [company]
        else:
            companies = list(Company.objects.filter(is_active=True, deleted_at__isnull=True))

        total_created = 0
        for company in companies:
            n = create_default_templates_for_company(company)
            total_created += n
            if n > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'{company.name} (id={company.id}) : {n} template(s) créé(s).')
                )
            else:
                self.stdout.write(f'{company.name} (id={company.id}) : aucun template à créer.')

        self.stdout.write(
            self.style.SUCCESS(f'Total : {total_created} template(s) créé(s) pour {len(companies)} entreprise(s).')
        )
