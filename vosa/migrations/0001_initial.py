# Generated by Django 3.0.5 on 2020-04-28 15:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Licence',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=48)),
                ('trading_name', models.CharField(max_length=48)),
                ('traffic_area', models.CharField(max_length=1)),
                ('licence_number', models.CharField(max_length=20, unique=True)),
                ('discs', models.PositiveIntegerField()),
                ('authorised_discs', models.PositiveIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Registration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registration_number', models.CharField(max_length=20, unique=True)),
                ('service_number', models.CharField(max_length=100)),
                ('description', models.CharField(max_length=255)),
                ('start_point', models.CharField(max_length=255)),
                ('finish_point', models.CharField(max_length=255)),
                ('via', models.CharField(blank=True, max_length=255)),
                ('subsidies_description', models.CharField(max_length=255)),
                ('subsidies_details', models.CharField(max_length=255)),
                ('licence_status', models.CharField(max_length=255)),
                ('registration_status', models.CharField(db_index=True, max_length=255)),
                ('traffic_area_office_covered_by_area', models.CharField(max_length=100)),
                ('licence', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vosa.Licence')),
            ],
        ),
        migrations.CreateModel(
            name='Variation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variation_number', models.PositiveIntegerField()),
                ('granted_date', models.DateField()),
                ('expiry_date', models.DateField()),
                ('effective_date', models.DateField(null=True)),
                ('date_received', models.DateField(null=True)),
                ('end_date', models.DateField(null=True)),
                ('service_type_other_details', models.TextField()),
                ('registration_status', models.CharField(max_length=255)),
                ('publication_text', models.TextField()),
                ('service_type_description', models.CharField(max_length=255)),
                ('short_notice', models.CharField(max_length=255)),
                ('authority_description', models.CharField(max_length=255)),
                ('registration', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='vosa.Registration')),
            ],
            options={
                'ordering': ('-variation_number',),
                'unique_together': {('registration', 'variation_number')},
            },
        ),
    ]
