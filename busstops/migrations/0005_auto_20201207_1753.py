# Generated by Django 3.1.4 on 2020-12-07 17:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('busstops', '0004_auto_20201116_1305'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='service',
            options={'ordering': ['id']},
        ),
    ]
