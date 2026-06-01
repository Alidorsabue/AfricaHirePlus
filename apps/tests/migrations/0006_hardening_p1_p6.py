"""
Migration de durcissement du module Tests (P1 → P6).

Ajouts :
  - Test : shuffle_questions, shuffle_options, questions_per_session, contrainte
    UniqueConstraint(company, access_code) conditionnelle.
  - Question : numeric_tolerance, validator points >= 1.
  - CandidateTestResult : is_passed, pending_review_points, last_seen_ip,
    question_order, indexe is_passed.
  - Answer : is_correct, pending_manual_review, index pending_manual_review.
  - Nouveau modèle : TestAccessGrant.
  - Nouveau modèle : TestAuditLog.
"""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.tests.models  # pour _generate_grant_token


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0005_rename_tests_answ_session_idx_tests_answe_session_4e0a1c_idx_and_more'),
        ('applications', '0006_ml_score_model'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---- Test : anti-triche P5 + contrainte unique access_code ----
        migrations.AddField(
            model_name='test',
            name='shuffle_questions',
            field=models.BooleanField(
                default=False,
                help_text="Si True, les questions sont présentées dans un ordre aléatoire propre à chaque candidat.",
            ),
        ),
        migrations.AddField(
            model_name='test',
            name='shuffle_options',
            field=models.BooleanField(
                default=False,
                help_text="Si True, les options des QCM sont mélangées par candidat.",
            ),
        ),
        migrations.AddField(
            model_name='test',
            name='questions_per_session',
            field=models.PositiveSmallIntegerField(
                null=True, blank=True,
                validators=[django.core.validators.MinValueValidator(1)],
                help_text=(
                    "Si défini, seul un sous-ensemble de N questions tirées aléatoirement "
                    "(parmi toutes celles du test) est présenté à chaque candidat."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name='test',
            constraint=models.UniqueConstraint(
                fields=('company', 'access_code'),
                condition=models.Q(access_code__gt=''),
                name='tests_test_access_code_unique_per_company',
            ),
        ),

        # ---- Question : numeric_tolerance + validator points ----
        migrations.AddField(
            model_name='question',
            name='numeric_tolerance',
            field=models.FloatField(
                null=True, blank=True,
                help_text=(
                    "Tolérance pour les questions numériques (proportion : 0.01 = ±1 %). "
                    "Si None, valeur par défaut globale 1 %. 0 = égalité stricte."
                ),
            ),
        ),
        migrations.AlterField(
            model_name='question',
            name='points',
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[django.core.validators.MinValueValidator(1)],
                help_text='Poids / score maximum pour la question. Doit être ≥ 1.',
            ),
        ),

        # ---- CandidateTestResult : champs P2/P4/P5 ----
        migrations.AddField(
            model_name='candidatetestresult',
            name='is_passed',
            field=models.BooleanField(
                null=True, blank=True, db_index=True,
                help_text='True si score >= test.passing_score (None tant que le scoring n\'est pas finalisé).',
            ),
        ),
        migrations.AddField(
            model_name='candidatetestresult',
            name='pending_review_points',
            field=models.DecimalField(
                max_digits=6, decimal_places=2, null=True, blank=True,
                help_text='Points en attente de révision manuelle (open_text / code / file_upload).',
            ),
        ),
        migrations.AddField(
            model_name='candidatetestresult',
            name='last_seen_ip',
            field=models.GenericIPAddressField(
                null=True, blank=True,
                help_text='Dernière IP vue (auto-save / tab-switch) — détection de changement de réseau.',
            ),
        ),
        migrations.AddField(
            model_name='candidatetestresult',
            name='question_order',
            field=models.JSONField(
                default=list, blank=True,
                help_text='Liste des IDs de questions présentées au candidat (P5 — shuffle / pool).',
            ),
        ),
        migrations.AddIndex(
            model_name='candidatetestresult',
            index=models.Index(fields=['is_passed'], name='tests_candi_is_pass_idx'),
        ),

        # ---- Answer : is_correct + pending_manual_review ----
        migrations.AddField(
            model_name='answer',
            name='is_correct',
            field=models.BooleanField(
                null=True, blank=True, db_index=True,
                help_text='True si la réponse est correcte (None pour open_text/code/file en attente de review).',
            ),
        ),
        migrations.AddField(
            model_name='answer',
            name='pending_manual_review',
            field=models.BooleanField(
                default=False, db_index=True,
                help_text='True pour les types nécessitant une correction manuelle (texte libre, code, fichier).',
            ),
        ),
        migrations.AddIndex(
            model_name='answer',
            index=models.Index(fields=['pending_manual_review'], name='tests_answe_pend_rev_idx'),
        ),

        # ---- Nouveau modèle : TestAccessGrant ----
        migrations.CreateModel(
            name='TestAccessGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('token', models.CharField(
                    default=apps.tests.models._generate_grant_token,
                    db_index=True, max_length=64, unique=True,
                )),
                ('is_revoked', models.BooleanField(default=False, db_index=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('used_at', models.DateTimeField(blank=True, null=True, help_text='Date de la première utilisation.')),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='test_access_grants',
                    to='applications.application',
                )),
                ('test', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='access_grants',
                    to='tests.test',
                )),
            ],
            options={
                'verbose_name': "Token d'accès test",
                'verbose_name_plural': "Tokens d'accès tests",
                'db_table': 'tests_testaccessgrant',
                'unique_together': {('test', 'application')},
                'indexes': [
                    models.Index(fields=['token', 'is_revoked'], name='tests_grant_token_rvk_idx'),
                    models.Index(fields=['application', 'is_revoked'], name='tests_grant_app_rvk_idx'),
                ],
            },
        ),

        # ---- Nouveau modèle : TestAuditLog ----
        migrations.CreateModel(
            name='TestAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('score_override', 'Modification manuelle du score'),
                        ('manual_review', "Notation d'une question en attente"),
                        ('status_change', 'Changement de statut'),
                        ('flag_toggled', 'Modification du flag (suspect / OK)'),
                        ('access_revoked', "Révocation d'un token d'accès"),
                    ],
                    db_index=True, max_length=30,
                )),
                ('old_value', models.JSONField(blank=True, null=True)),
                ('new_value', models.JSONField(blank=True, null=True)),
                ('reason', models.TextField(blank=True)),
                ('client_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='test_audit_entries',
                    to=settings.AUTH_USER_MODEL,
                    help_text="Utilisateur qui a effectué l'action (recruteur, admin).",
                )),
                ('answer', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='audit_log',
                    to='tests.answer',
                    help_text='Réponse concernée (si applicable).',
                )),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audit_log',
                    to='tests.candidatetestresult',
                )),
            ],
            options={
                'verbose_name': "Entrée d'audit test",
                'verbose_name_plural': "Journal d'audit tests",
                'db_table': 'tests_testauditlog',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['session', 'action'], name='tests_audit_sess_act_idx'),
                    models.Index(fields=['actor', 'created_at'], name='tests_audit_actor_idx'),
                ],
            },
        ),
    ]
