"""P10 — Renforcement candidatures : ApplicationAuditLog + ApplicationNote."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0006_ml_score_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ApplicationAuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('status_change', 'Changement de statut'),
                        ('score_override', 'Override score'),
                        ('manual_override', 'Override manuel'),
                        ('withdrawn', 'Retrait candidat'),
                        ('run_screening', 'Relance screening'),
                        ('note_updated', 'Note interne modifiée'),
                    ],
                    db_index=True,
                    max_length=32,
                )),
                ('payload_before', models.JSONField(blank=True, default=dict, help_text='Snapshot des champs concernés avant modification.')),
                ('payload_after', models.JSONField(blank=True, default=dict, help_text='Snapshot des champs concernés après modification.')),
                ('reason', models.TextField(blank=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_logs',
                    to='applications.application',
                )),
                ('actor', models.ForeignKey(
                    blank=True,
                    help_text="User à l'origine de l'action (null si système / signal).",
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='application_audit_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'applications_audit_log',
                'verbose_name': 'Journal candidature',
                'verbose_name_plural': 'Journaux candidatures',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['application', 'created_at'], name='applications_audit_app_ts_idx'),
                    models.Index(fields=['action', 'created_at'], name='applications_audit_act_ts_idx'),
                    models.Index(fields=['actor', 'created_at'], name='applications_audit_actor_ts_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ApplicationNote',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField()),
                ('is_pinned', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='internal_notes',
                    to='applications.application',
                )),
                ('author', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='application_notes',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'applications_note',
                'verbose_name': 'Note candidature',
                'verbose_name_plural': 'Notes candidatures',
                'ordering': ['-is_pinned', '-created_at'],
                'indexes': [
                    models.Index(fields=['application', 'created_at'], name='applications_note_app_ts_idx'),
                ],
            },
        ),
    ]
