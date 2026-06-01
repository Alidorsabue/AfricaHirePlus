"""
P9 — Audit log + nouveaux types de templates (test/corrector).

  * Étend `EmailTemplate.TemplateType` (ajout de 4 nouveaux choix).
  * Crée le modèle `EmailLog` pour audit complet des envois.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0002_allow_blank_body_html'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailtemplate',
            name='template_type',
            field=models.CharField(
                choices=[
                    ('application_received', 'Candidature reçue'),
                    ('application_rejected', 'Candidature refusée'),
                    ('shortlist_notification', 'Notification shortlist'),
                    ('interview_invitation', 'Invitation entretien'),
                    ('offer_letter', "Lettre d'offre"),
                    ('test_invitation', 'Invitation test'),
                    ('test_submitted', 'Test soumis (recruteur)'),
                    ('test_expired', 'Test expiré (candidat)'),
                    ('corrector_invitation', 'Invitation correcteur'),
                    ('corrector_revoked', 'Accès correcteur révoqué'),
                    ('reminder', 'Relance'),
                    ('custom', 'Personnalisé'),
                ],
                db_index=True,
                default='custom',
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name='EmailLog',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template_type', models.CharField(blank=True, db_index=True, default='', max_length=40)),
                ('recipient_email', models.EmailField(db_index=True, max_length=254)),
                ('subject', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'En attente'),
                        ('sent', 'Envoyé'),
                        ('failed', 'Échec'),
                        ('skipped', 'Ignoré'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('provider', models.CharField(blank=True, default='', max_length=40)),
                ('provider_message_id', models.CharField(blank=True, db_index=True, default='', max_length=255)),
                ('error_message', models.TextField(blank=True, default='')),
                ('sent_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('related_application_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('related_object_type', models.CharField(blank=True, default='', max_length=80)),
                ('related_object_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='email_logs',
                    to='companies.company',
                )),
            ],
            options={
                'verbose_name': "Log d'email",
                'verbose_name_plural': "Logs d'emails",
                'db_table': 'emails_emaillog',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(
                fields=['company', 'status'], name='emails_emai_company_status_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(
                fields=['template_type', 'status'], name='emails_emai_tplstatus_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='emaillog',
            index=models.Index(
                fields=['recipient_email', 'created_at'], name='emails_emai_recipient_dt_idx',
            ),
        ),
    ]
