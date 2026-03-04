# ATS: preselection_score, selection_score, manual override, email_sent, status choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('applications', '0003_candidate_user_and_extended_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='preselection_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='selection_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='is_manually_adjusted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='application',
            name='manual_override_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='application',
            name='manually_added_to_shortlist',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='application',
            name='email_sent',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='application',
            name='status',
            field=models.CharField(
                choices=[
                    ('applied', 'Postulé'),
                    ('preselected', 'Pré-sélectionné'),
                    ('rejected_preselection', 'Refusé (présélection)'),
                    ('shortlisted', 'Shortlisté'),
                    ('rejected_selection', 'Refusé (sélection)'),
                    ('interview', 'En entretien'),
                    ('offer', 'Offre envoyée'),
                    ('hired', 'Embauché'),
                    ('rejected', 'Refusé'),
                    ('withdrawn', 'Retirée'),
                ],
                db_index=True,
                default='applied',
                max_length=24,
            ),
        ),
    ]
