"""
Crée un utilisateur Super Admin (role=super_admin, is_staff=True, is_superuser=True).
Usage :
  python manage.py create_superadmin
  python manage.py create_superadmin --username admin --email admin@example.com --no-input  # avec mot de passe en variable SUPERADMIN_PASSWORD
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée un utilisateur Super Admin (accès plateforme complet, sans entreprise)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help="Nom d'utilisateur (sinon demandé interactivement).",
        )
        parser.add_argument(
            '--email',
            type=str,
            help="Adresse e-mail (sinon demandée interactivement).",
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help="Ne pas demander de saisie. Utilise SUPERADMIN_PASSWORD en variable d'environnement pour le mot de passe.",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        if options['no_input']:
            username = options.get('username')
            email = options.get('email')
            if not username or not email:
                self.stderr.write(
                    self.style.ERROR('Avec --no-input, fournissez --username et --email.')
                )
                return
            import os
            password = os.environ.get('SUPERADMIN_PASSWORD')
            if not password:
                self.stderr.write(
                    self.style.ERROR(
                        'Variable d\'environnement SUPERADMIN_PASSWORD requise avec --no-input.'
                    )
                )
                return
        else:
            username = options.get('username') or input('Username: ').strip()
            email = options.get('email') or input('Email: ').strip()
            password = None
            while not password or len(password) < 8:
                password = input('Password (min. 8 caractères): ').strip()
                if password and len(password) < 8:
                    self.stderr.write(self.style.WARNING('Au moins 8 caractères.'))

        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f"L'utilisateur '{username}' existe déjà."))
            return
        if email and User.objects.filter(email__iexact=email).exists():
            self.stderr.write(self.style.ERROR(f"Un utilisateur avec l'email '{email}' existe déjà."))
            return

        user = User.objects.create_user(
            username=username,
            email=email or '',
            password=password,
            role=User.Role.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            company=None,
        )
        user.save()
        self.stdout.write(
            self.style.SUCCESS(f"Super Admin créé : {user.username} (email={user.email})")
        )
