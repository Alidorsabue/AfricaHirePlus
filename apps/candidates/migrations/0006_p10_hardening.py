"""P10 — Renforcement candidats : tags, is_anonymized, anonymized_at + indexes."""
from django.db import migrations, models


def normalize_emails_lowercase(apps, schema_editor):
    """Normalise les emails existants en lowercase (idempotent)."""
    Candidate = apps.get_model('candidates', 'Candidate')
    for c in Candidate.objects.all().only('id', 'email'):
        if c.email and c.email != c.email.lower():
            c.email = c.email.lower()
            c.save(update_fields=['email'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('candidates', '0005_alter_candidate_education_alter_candidate_experience_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidate',
            name='tags',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Tags libres pour le pool (ex: "top-talent", "rappeler 2025-03").',
            ),
        ),
        migrations.AddField(
            model_name='candidate',
            name='is_anonymized',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Candidat anonymisé (RGPD) : les champs identifiants sont vidés.',
            ),
        ),
        migrations.AddField(
            model_name='candidate',
            name='anonymized_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name='candidate',
            index=models.Index(fields=['company', 'is_anonymized'], name='cand_company_anon_idx'),
        ),
        migrations.AddIndex(
            model_name='candidate',
            index=models.Index(fields=['company', 'created_at'], name='cand_company_created_idx'),
        ),
        migrations.AddIndex(
            model_name='candidate',
            index=models.Index(fields=['company', 'updated_at'], name='cand_company_updated_idx'),
        ),
        migrations.RunPython(normalize_emails_lowercase, noop_reverse),
    ]
