"""
Migration P8 — Rôle Correcteur externe.

Ajouts :
  - CandidateTestResult.display_code (code anonymisé pour les correcteurs).
  - Nouveau modèle CorrectorAssignment (token magique, sans compte).
  - TestAuditLog.corrector (FK alternative à actor pour les correcteurs).
  - 3 nouvelles actions d'audit (CORRECTOR_ASSIGNED, CORRECTOR_REVOKED, CORRECTOR_REVIEW).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.tests.models  # pour _generate_corrector_token


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0006_hardening_p1_p6'),
        ('applications', '0006_ml_score_model'),
        ('companies', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---- display_code anonymisé ----
        migrations.AddField(
            model_name='candidatetestresult',
            name='display_code',
            field=models.CharField(
                blank=True, db_index=True, max_length=12,
                help_text=(
                    "Code d'affichage anonymisé (ex. 'C-A3F9B2C1') unique au sein du test. "
                    "Présenté au correcteur à la place du nom du candidat. "
                    "Généré paresseusement lors de la première vue correcteur."
                ),
            ),
        ),

        # ---- Nouveau modèle : CorrectorAssignment ----
        migrations.CreateModel(
            name='CorrectorAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(
                    db_index=True, max_length=254,
                    help_text="Email du correcteur. C'est l'identité fonctionnelle.",
                )),
                ('full_name', models.CharField(
                    blank=True, max_length=255,
                    help_text="Nom optionnel pour personnaliser l'email d'invitation.",
                )),
                ('token', models.CharField(
                    default=apps.tests.models._generate_corrector_token,
                    db_index=True, max_length=96, unique=True,
                    help_text='Token signé URL-safe pour authentification sans compte.',
                )),
                ('all_candidates', models.BooleanField(
                    default=True,
                    help_text=(
                        "Si True, le correcteur voit toutes les sessions SCORED de ce test "
                        "(y compris les soumissions futures). Si False, restreint à "
                        "assigned_applications."
                    ),
                )),
                ('is_revoked', models.BooleanField(default=False, db_index=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(
                    blank=True, db_index=True, null=True,
                    help_text="Date d'expiration du token (None = pas d'expiration).",
                )),
                ('first_used_at', models.DateTimeField(blank=True, null=True)),
                ('last_used_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('use_count', models.PositiveIntegerField(default=0)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='corrector_assignments',
                    to='companies.company',
                    help_text='Entreprise propriétaire (multi-tenant).',
                )),
                ('test', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='corrector_assignments',
                    to='tests.test',
                )),
                ('assigned_applications', models.ManyToManyField(
                    blank=True, related_name='corrector_assignments',
                    to='applications.application',
                    help_text=(
                        "Candidatures explicitement attribuées (utilisé si "
                        "all_candidates=False). Le correcteur ne verra QUE ces sessions."
                    ),
                )),
                ('assigned_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='correctors_assigned',
                    to=settings.AUTH_USER_MODEL,
                    help_text='Recruteur ayant créé cette assignation.',
                )),
                ('revoked_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='correctors_revoked',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Assignation correcteur',
                'verbose_name_plural': 'Assignations correcteurs',
                'db_table': 'tests_correctorassignment',
                'ordering': ['-created_at'],
                'unique_together': {('test', 'email')},
                'indexes': [
                    models.Index(fields=['token', 'is_revoked'], name='tests_corr_token_rvk_idx'),
                    models.Index(fields=['test', 'is_revoked'], name='tests_corr_test_rvk_idx'),
                    models.Index(fields=['company', 'is_revoked'], name='tests_corr_co_rvk_idx'),
                ],
            },
        ),

        # ---- TestAuditLog : ajout corrector FK + nouvelles actions ----
        migrations.AddField(
            model_name='testauditlog',
            name='corrector',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='audit_entries',
                to='tests.correctorassignment',
                help_text="Acteur correcteur externe (si l'action a été faite via un token correcteur).",
            ),
        ),
        migrations.AlterField(
            model_name='testauditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('score_override', 'Modification manuelle du score'),
                    ('manual_review', "Notation d'une question en attente"),
                    ('status_change', 'Changement de statut'),
                    ('flag_toggled', 'Modification du flag (suspect / OK)'),
                    ('access_revoked', "Révocation d'un token d'accès"),
                    ('corrector_assigned', "Assignation d'un correcteur"),
                    ('corrector_revoked', "Révocation d'un correcteur"),
                    ('corrector_review', 'Notation par un correcteur externe'),
                ],
                db_index=True, max_length=30,
            ),
        ),
        migrations.AddIndex(
            model_name='testauditlog',
            index=models.Index(
                fields=['corrector', 'created_at'],
                name='tests_audit_corr_idx',
            ),
        ),
    ]
