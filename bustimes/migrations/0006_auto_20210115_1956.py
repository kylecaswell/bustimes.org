# Generated by Django 3.1.5 on 2021-01-15 19:56

import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0006_auto_20201225_0004'),
        ('bustimes', '0005_auto_20201224_2350'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehicleType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=50)),
                ('description', models.CharField(blank=True, max_length=100)),
            ],
        ),
        migrations.AlterField(
            model_name='route',
            name='geometry',
            field=django.contrib.gis.db.models.fields.MultiLineStringField(blank=True, editable=False, null=True, srid=4326),
        ),
        migrations.CreateModel(
            name='Garage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(blank=True, max_length=50)),
                ('name', models.CharField(blank=True, max_length=100)),
                ('location', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('address', models.CharField(blank=True, max_length=255)),
                ('operator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='busstops.operator')),
            ],
        ),
        migrations.AddField(
            model_name='trip',
            name='garage',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='bustimes.garage'),
        ),
    ]
