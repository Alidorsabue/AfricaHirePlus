"""
Supprime les EmailLog plus vieux que `EMAIL_LOG_RETENTION_DAYS` jours.

Usage :
  python manage.py purge_old_email_logs            # respecte EMAIL_LOG_RETENTION_DAYS
  python manage.py purge_old_email_logs --days 30  # override explicite
  python manage.py purge_old_email_logs --dry-run  # n'efface rien, affiche le décompte
  python manage.py purge_old_email_logs --status failed  # purge uniquement les échecs

Cron recommandé : 1 fois par semaine.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.emails.models import EmailLog


class Command(BaseCommand):
    help = (
        'Supprime les EmailLog plus vieux que N jours '
        '(défaut : EMAIL_LOG_RETENTION_DAYS settings).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=None,
            help='Nombre de jours de rétention (override settings.EMAIL_LOG_RETENTION_DAYS).',
        )
        parser.add_argument(
            '--status', type=str, default='', choices=['', 'sent', 'failed', 'skipped', 'pending'],
            help='Filtre par statut (par défaut : tous).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Affiche le décompte sans supprimer.',
        )

    def handle(self, *args, **opts):
        days = opts['days']
        if days is None:
            days = int(getattr(settings, 'EMAIL_LOG_RETENTION_DAYS', 90) or 0)
        if days <= 0:
            self.stdout.write(self.style.WARNING(
                'Rétention désactivée (days <= 0). Aucune purge.'
            ))
            return

        cutoff = timezone.now() - timedelta(days=days)
        qs = EmailLog.objects.filter(created_at__lt=cutoff)

        status_filter = opts['status']
        if status_filter:
            qs = qs.filter(status=status_filter)

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS(
                f'Aucun log à purger (cutoff = {cutoff.isoformat()}).'
            ))
            return

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] {count} log(s) seraient supprimés (cutoff={cutoff.isoformat()}'
                f'{", status="+status_filter if status_filter else ""}).'
            ))
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'{deleted} log(s) supprimé(s) (cutoff={cutoff.isoformat()}).'
        ))
