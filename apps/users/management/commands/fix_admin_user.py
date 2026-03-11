"""
Répare un utilisateur existant pour qu’il puisse se connecter à l’admin Django :
- Re-hash le mot de passe (si il a été mis en base en clair, la connexion échoue).
- Corrige le rôle en 'super_admin' si besoin (valeur attendue par le modèle).
Usage :
  python manage.py fix_admin_user Alidorsabue
  python manage.py fix_admin_user Alidorsabue --no-input  # mot de passe dans ADMIN_PASSWORD
"""
import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Répare un utilisateur (mot de passe hashé + rôle super_admin) pour la connexion admin."

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help="Nom d'utilisateur à réparer.")
        parser.add_argument(
            '--no-input',
            action='store_true',
            help="Utiliser la variable d'environnement ADMIN_PASSWORD pour le mot de passe.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username'].strip()
        if not username:
            raise CommandError("Indiquez un username.")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Utilisateur '{username}' introuvable.")

        if options['no_input']:
            password = os.environ.get('ADMIN_PASSWORD')
            if not password:
                raise CommandError(
                    "Avec --no-input, définissez la variable d'environnement ADMIN_PASSWORD."
                )
        else:
            password = input("Nouveau mot de passe (min. 8 caractères) : ").strip()
            while len(password) < 8:
                self.stderr.write(self.style.WARNING("Au moins 8 caractères."))
                password = input("Nouveau mot de passe : ").strip()

        user.set_password(password)
        user.role = User.Role.SUPER_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['password', 'role', 'is_staff', 'is_superuser'])

        self.stdout.write(
            self.style.SUCCESS(
                f"Utilisateur '{username}' mis à jour : mot de passe hashé, role=super_admin, is_staff=True, is_superuser=True. Vous pouvez vous connecter à /admin/."
            )
        )
