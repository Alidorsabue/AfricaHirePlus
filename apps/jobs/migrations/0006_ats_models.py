# ATS: deadline, PreselectionSettings, SelectionSettings

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0005_add_description_document_again'),
    ]

    operations = [
        migrations.AddField(
            model_name='joboffer',
            name='deadline',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='Date limite de candidature (optionnel).',
                null=True,
            ),
        ),
        migrations.CreateModel(
            name='PreselectionSettings',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job_offer', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True,
                    related_name='preselection_settings',
                    serialize=False,
                    to='jobs.joboffer',
                )),
                ('criteria_json', models.JSONField(blank=True, default=dict)),
                ('score_threshold', models.FloatField(default=60.0)),
                ('max_candidates', models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Paramètres de présélection',
                'verbose_name_plural': 'Paramètres de présélection',
                'db_table': 'jobs_preselectionsettings',
            },
        ),
        migrations.CreateModel(
            name='SelectionSettings',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job_offer', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True,
                    related_name='selection_settings',
                    serialize=False,
                    to='jobs.joboffer',
                )),
                ('criteria_json', models.JSONField(blank=True, default=dict)),
                ('score_threshold', models.FloatField(default=60.0)),
                ('max_candidates', models.PositiveIntegerField(blank=True, null=True)),
                ('selection_mode', models.CharField(
                    choices=[('auto', 'Automatique'), ('semi_automatic', 'Semi-automatique')],
                    db_index=True,
                    default='semi_automatic',
                    max_length=20,
                )),
            ],
            options={
                'verbose_name': 'Paramètres de sélection',
                'verbose_name_plural': 'Paramètres de sélection',
                'db_table': 'jobs_selectionsettings',
            },
        ),
    ]
