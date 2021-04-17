# Generated by Django 3.2 on 2021-04-17 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vosa', '0002_auto_20201121_0959'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='registration',
            name='licence_status',
        ),
        migrations.RemoveField(
            model_name='variation',
            name='expiry_date',
        ),
        migrations.RemoveField(
            model_name='variation',
            name='granted_date',
        ),
        migrations.AddField(
            model_name='licence',
            name='expiry_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='licence',
            name='licence_status',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='licence',
            name='description',
            field=models.CharField(choices=[('Restricted', 'Restricted'), ('Standard International', 'Standard International'), ('Standard National', 'Standard National')], max_length=22),
        ),
        migrations.AlterField(
            model_name='licence',
            name='granted_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='licence',
            name='trading_name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='licence',
            name='traffic_area',
            field=models.CharField(choices=[('H', 'West of England'), ('D', 'West Midlands'), ('G', 'Wales'), ('K', 'London and the South East of England'), ('M', 'Scotland'), ('C', 'North West of England'), ('B', 'North East of England'), ('F', 'East of England')], max_length=1),
        ),
        migrations.AlterField(
            model_name='variation',
            name='date_received',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='variation',
            name='effective_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='variation',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
