"""
Envoie un e-mail de test pour vérifier la configuration SMTP.
Usage:
  python manage.py send_test_email destinataire@example.com
"""
from django.core.mail import send_mail
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envoie un e-mail de test à l'adresse indiquée pour vérifier la configuration SMTP."

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help="Adresse e-mail du destinataire du message de test.",
        )

    def handle(self, *args, **options):
        to_email = options['email'].strip()
        if not to_email or '@' not in to_email:
            self.stderr.write(self.style.ERROR('Indiquez une adresse e-mail valide.'))
            return

        backend = getattr(settings, 'EMAIL_BACKEND', '')
        if 'console' in backend:
            self.stdout.write(
                self.style.WARNING(
                    'Backend actuel : console (les e-mails ne partent pas vraiment). '
                    'Configurez SMTP dans .env pour un envoi réel.'
                )
            )

        try:
            send_mail(
                subject='[AfricaHirePlus] Test d’envoi d’e-mail',
                message='Ceci est un message de test. Si vous le recevez, la configuration SMTP fonctionne.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=(
                    '<p>Ceci est un <strong>message de test</strong>.</p>'
                    '<p>Si vous le recevez, la configuration SMTP fonctionne correctement.</p>'
                ),
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f'E-mail de test envoyé à {to_email}.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erreur d’envoi : {e}'))
