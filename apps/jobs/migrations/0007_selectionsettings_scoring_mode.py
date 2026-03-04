# Add scoring_mode, rule_based_weight, ml_weight to SelectionSettings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0006_ats_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='selectionsettings',
            name='scoring_mode',
            field=models.CharField(
                choices=[
                    ('rule_based', 'Règles uniquement'),
                    ('hybrid', 'Hybride (règles + ML)'),
                    ('ml_only', 'ML uniquement'),
                ],
                db_index=True,
                default='rule_based',
                help_text='RULE_BASED: score règles ; HYBRID: combinaison règles + ML ; ML_ONLY: score ML seul.',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='selectionsettings',
            name='rule_based_weight',
            field=models.FloatField(
                default=0.6,
                help_text='Poids du score rule-based dans le mode HYBRID (final = rule*weight + ml*(1-weight)).',
            ),
        ),
        migrations.AddField(
            model_name='selectionsettings',
            name='ml_weight',
            field=models.FloatField(
                default=0.4,
                help_text='Poids du score ML dans le mode HYBRID.',
            ),
        ),
    ]
