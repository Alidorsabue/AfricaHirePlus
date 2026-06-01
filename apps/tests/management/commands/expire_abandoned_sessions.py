"""
Commande de maintenance : expire automatiquement les sessions de test abandonnées
(timer global dépassé, candidat n'a jamais soumis).

Usage :
    python manage.py expire_abandoned_sessions
    python manage.py expire_abandoned_sessions --notify    # envoie un email au candidat
    python manage.py expire_abandoned_sessions --dry-run   # liste sans modifier

À planifier via cron / Celery beat / Railway Schedule toutes les 5–15 minutes.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.tests.models import CandidateTestResult


class Command(BaseCommand):
    help = "Expire les sessions IN_PROGRESS dont le timer est dépassé."

    def add_arguments(self, parser):
        parser.add_argument(
            '--notify',
            action='store_true',
            help="Envoie un email au candidat pour chaque session expirée.",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les sessions qui seraient expirées sans rien modifier.',
        )

    def handle(self, *args, **options):
        from apps.tests.services import expire_session_if_needed

        notify = options['notify']
        dry_run = options['dry_run']

        # Candidates pour l'expiration : status IN_PROGRESS avec started_at + duration < now
        # On filtre en Python car duration_minutes est sur le Test (relation).
        sessions = (
            CandidateTestResult.objects.filter(
                status=CandidateTestResult.Status.IN_PROGRESS,
                is_completed=False,
                started_at__isnull=False,
            )
            .select_related('test', 'application__candidate', 'application__job_offer')
        )
        now = timezone.now()
        expired_count = 0
        for result in sessions:
            duration = result.test.duration_minutes
            if not duration:
                continue
            deadline = result.started_at + timedelta(minutes=duration)
            if now <= deadline:
                continue
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Session #{result.id} (test={result.test.title}, "
                    f"candidat={result.application.candidate.email}) → EXPIRED"
                )
                expired_count += 1
                continue
            if expire_session_if_needed(result):
                expired_count += 1
                if notify:
                    try:
                        from apps.emails.services import send_test_expired_notification
                        send_test_expired_notification(result)
                    except Exception as e:
                        self.stderr.write(f"Email échoué pour session #{result.id}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{expired_count} session(s) expirée(s)"
                + (' (dry-run)' if dry_run else '')
                + (' avec notification email' if notify and not dry_run else '')
            )
        )
