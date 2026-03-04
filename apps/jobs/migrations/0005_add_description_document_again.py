# Re-add description_document (after 0004 removed it)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0004_remove_joboffer_description_document_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='joboffer',
            name='description_document',
            field=models.FileField(
                blank=True,
                help_text='PDF ou Word : fiche offre à afficher aux candidats.',
                null=True,
                upload_to='jobs/documents/%Y/%m/',
            ),
        ),
        migrations.AlterField(
            model_name='joboffer',
            name='description',
            field=models.TextField(blank=True, help_text='Optionnel si un document est joint.'),
        ),
    ]
