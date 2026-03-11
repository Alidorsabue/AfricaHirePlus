# Generated manually for CompanyLicense (licence entreprise)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanyLicense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('license_key', models.CharField(db_index=True, max_length=32, unique=True)),
                ('duration_months', models.PositiveSmallIntegerField(
                    choices=[(3, '3 mois'), (6, '6 mois'), (9, '9 mois'), (12, '1 an'), (24, '2 ans')],
                    default=12,
                )),
                ('start_date', models.DateField(db_index=True)),
                ('end_date', models.DateField(db_index=True)),
                ('company', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='license',
                    to='companies.company',
                )),
            ],
            options={
                'verbose_name': 'Licence entreprise',
                'verbose_name_plural': 'Licences entreprises',
                'db_table': 'companies_companylicense',
            },
        ),
    ]
