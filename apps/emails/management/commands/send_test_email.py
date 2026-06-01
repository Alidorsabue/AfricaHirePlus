"""
Envoie un e-mail de test pour vérifier la configuration SMTP.
Usage:
  python manage.py send_test_email destinataire@exemple.com
  python manage.py send_test_email --list-companies
  python manage.py send_test_email destinataire@exemple.com --company-slug mon-entreprise
  python manage.py send_test_email destinataire@exemple.com --company-email rh@client.com
  python manage.py send_test_email destinataire@exemple.com --company-id 1
  python manage.py send_test_email --show-config
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.companies.models import Company
from apps.core.email_utils import get_from_email, get_from_email_for_company
from apps.emails.dispatch import dispatch_email
from apps.emails.models import EmailLog


class Command(BaseCommand):
    help = "Envoie un e-mail de test à l'adresse indiquée pour vérifier la configuration SMTP."

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            nargs='?',
            default='',
            help="Adresse e-mail du destinataire du message de test.",
        )
        parser.add_argument(
            '--show-config',
            action='store_true',
            help='Affiche la configuration e-mail actuelle (sans mot de passe) et quitte.',
        )
        parser.add_argument(
            '--company-id',
            type=int,
            default=None,
            metavar='ID',
            help="Teste l’expéditeur comme pour une entreprise (utilise company.email + nom si renseigné).",
        )
        parser.add_argument(
            '--company-slug',
            type=str,
            default='',
            metavar='SLUG',
            help='Même chose en utilisant le slug unique de l’entreprise (voir --list-companies).',
        )
        parser.add_argument(
            '--company-email',
            type=str,
            default='',
            metavar='EMAIL',
            help='Même chose en ciblant l’entreprise par son champ e-mail (correspondance exacte).',
        )
        parser.add_argument(
            '--list-companies',
            action='store_true',
            help='Affiche id, slug, nom et e-mail de chaque entreprise puis quitte.',
        )

    def handle(self, *args, **options):
        if options['list_companies']:
            self._list_companies()
            return

        if options['show_config']:
            self._print_config()
            return

        to_email = (options['email'] or '').strip()
        if not to_email or '@' not in to_email:
            self.stderr.write(self.style.ERROR('Indiquez une adresse e-mail valide ou utilisez --show-config.'))
            return

        backend = getattr(settings, 'EMAIL_BACKEND', '')
        if 'console' in backend:
            self.stdout.write(
                self.style.WARNING(
                    'Backend actuel : console (les e-mails ne partent pas vraiment). '
                    'Configurez SMTP dans .env pour un envoi réel.'
                )
            )

        self._print_config()

        try:
            company = self._resolve_company(options)
        except CommandError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        if company is not None:
            self.stdout.write(
                f"  Expéditeur (From) pour cette entreprise = {get_from_email_for_company(company)}"
            )

        from_addr = get_from_email_for_company(company) if company is not None else get_from_email()
        self.stdout.write(f"  From utilisé      = {from_addr}")

        log = dispatch_email(
            company=company,
            template_type='diagnostic',
            recipient=to_email,
            subject='[AfricaHirePlus] Test d\'envoi d\'email (diagnostic)',
            body_html=(
                "<p>Ceci est un <strong>message de test</strong> envoyé par "
                "<code>python manage.py send_test_email</code>.</p>"
                "<p>Si vous le recevez, la configuration emails (Brevo / SMTP) "
                "fonctionne correctement.</p>"
            ),
            preheader='Test de configuration emails',
            footer_note='Cet email a été émis manuellement pour diagnostic.',
            tags=['diagnostic'],
        )

        if log is None:
            self.stdout.write(self.style.WARNING(
                'Audit log désactivé — envoi tenté mais aucun EmailLog créé.'
            ))
            self.stdout.write(self.style.SUCCESS(f'Demande d\'envoi soumise à {to_email}.'))
            return

        if log.status == EmailLog.Status.SENT:
            self.stdout.write(self.style.SUCCESS(
                f'E-mail de test envoyé à {to_email} (id audit={log.pk}, '
                f'message_id="{log.provider_message_id or "—"}").'
            ))
        elif log.status == EmailLog.Status.SKIPPED:
            self.stderr.write(self.style.WARNING(
                f'Envoi ignoré (raison : {log.error_message}).'
            ))
        else:
            self.stderr.write(self.style.ERROR(
                f'Échec d\'envoi (status={log.status}). Erreur : {log.error_message}'
            ))

    def _resolve_company(self, options) -> Company | None:
        """Retourne l’entreprise ciblée ou None. Lève CommandError si critères invalides ou introuvable."""
        cid = options.get('company_id')
        slug = (options.get('company_slug') or '').strip()
        cemail = (options.get('company_email') or '').strip()
        n = sum([cid is not None, bool(slug), bool(cemail)])
        if n > 1:
            raise CommandError(
                'Utilisez un seul parmi --company-id, --company-slug, --company-email.'
            )
        if cid is not None:
            try:
                return Company.objects.get(pk=cid)
            except Company.DoesNotExist:
                raise CommandError(f'Aucune entreprise avec l’id {cid}.')
        if slug:
            try:
                return Company.objects.get(slug__iexact=slug)
            except Company.DoesNotExist:
                raise CommandError(f'Aucune entreprise avec le slug « {slug} ».')
        if cemail:
            qs = Company.objects.filter(email__iexact=cemail)
            count = qs.count()
            if count == 0:
                raise CommandError(f'Aucune entreprise avec l’e-mail « {cemail} ».')
            if count > 1:
                raise CommandError(
                    'Plusieurs entreprises partagent cet e-mail ; utilisez --company-slug ou --company-id.'
                )
            return qs.first()
        return None

    def _list_companies(self):
        rows = list(Company.objects.order_by('id').values_list('id', 'slug', 'name', 'email'))
        if not rows:
            self.stdout.write('Aucune entreprise en base.')
            return
        self.stdout.write('Entreprises (id | slug | nom | e-mail expéditeur) :')
        for pk, sl, name, em in rows:
            em = em or '(vide)'
            self.stdout.write(f"  {pk}\t{sl}\t{name}\t{em}")

    def _print_config(self):
        backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
        provider = 'unknown'
        if 'brevo' in backend.lower():
            provider = 'Brevo (API REST)'
        elif 'smtp' in backend.lower():
            provider = 'SMTP'
        elif 'console' in backend.lower():
            provider = 'Console (aucun envoi réel)'
        elif 'locmem' in backend.lower():
            provider = 'Locmem (tests)'

        self.stdout.write('Configuration e-mail actuelle :')
        self.stdout.write(f"  Provider détecté  = {provider}")
        self.stdout.write(f"  EMAIL_BACKEND     = {backend}")
        # Brevo API
        brevo_key = getattr(settings, 'BREVO_API_KEY', '') or ''
        self.stdout.write(f"  BREVO_API_KEY     = {'***' if brevo_key else '(vide)'}")
        if brevo_key:
            self.stdout.write(f"  BREVO_API_URL     = {getattr(settings, 'BREVO_API_URL', '')}")
            self.stdout.write(f"  BREVO_API_TIMEOUT = {getattr(settings, 'BREVO_API_TIMEOUT', '')}s")
        # SMTP
        self.stdout.write(f"  EMAIL_HOST        = {getattr(settings, 'EMAIL_HOST', '') or '(vide)'}")
        self.stdout.write(f"  EMAIL_PORT        = {getattr(settings, 'EMAIL_PORT', '')}")
        self.stdout.write(f"  EMAIL_USE_TLS     = {getattr(settings, 'EMAIL_USE_TLS', '')}")
        self.stdout.write(f"  EMAIL_USE_SSL     = {getattr(settings, 'EMAIL_USE_SSL', '')}")
        self.stdout.write(f"  EMAIL_TIMEOUT     = {getattr(settings, 'EMAIL_TIMEOUT', '')}")
        user = getattr(settings, 'EMAIL_HOST_USER', '') or ''
        self.stdout.write(f"  EMAIL_HOST_USER   = {user or '(vide)'}")
        pwd = getattr(settings, 'EMAIL_HOST_PASSWORD', '') or ''
        self.stdout.write(f"  EMAIL_HOST_PASSWORD = {'***' if pwd else '(vide)'}")
        # Branding
        self.stdout.write(f"  Expéditeur (From) = {get_from_email()}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL = {getattr(settings, 'DEFAULT_FROM_EMAIL', '')}")
        self.stdout.write(f"  SERVER_EMAIL      = {getattr(settings, 'SERVER_EMAIL', '')}")
        # Audit
        retention = getattr(settings, 'EMAIL_LOG_RETENTION_DAYS', 0)
        audit_on = getattr(settings, 'EMAIL_AUDIT_LOG_ENABLED', True)
        self.stdout.write(f"  EMAIL_AUDIT_LOG    = {'ON' if audit_on else 'OFF'} (retention={retention}j)")
