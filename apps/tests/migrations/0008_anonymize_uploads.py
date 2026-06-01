"""
P8c — Anonymisation des uploads de réponse / attachment de question.

Change uniquement les `upload_to` (callable UUID) → aucun fichier existant
n'est déplacé. Les anciens fichiers gardent leur nom original ; les NOUVEAUX
uploads seront automatiquement renommés en UUID.

Si l'équipe veut renommer les anciens fichiers, créer une commande de
maintenance dédiée (hors-scope ici).
"""
from django.db import migrations, models

import apps.tests.models


class Migration(migrations.Migration):

    dependencies = [
        ('tests', '0007_corrector_role'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answer',
            name='file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=apps.tests.models._anonymized_answer_file_path,
                help_text=(
                    'Fichier réponse (Excel, Word, PDF, PowerPoint, PBIX, etc.). '
                    'P8c — Stocké sous un nom UUID pour ne pas fuiter l\'identité '
                    'du candidat (ex. "cv_jean.pdf") vers le correcteur externe.'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='question',
            name='attachment',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=apps.tests.models._anonymized_question_attachment_path,
                help_text=(
                    "Fichier ressource (énoncé détaillé, jeu de données, template, etc.). "
                    "P8c — Stocké sous un nom UUID pour anonymisation."
                ),
            ),
        ),
    ]
