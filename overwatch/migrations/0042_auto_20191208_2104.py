# Generated by Django 2.1.5 on 2019-12-08 21:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('overwatch', '0041_auto_20191208_2035'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='bot',
            options={'ordering': ['name', 'exchange_account__identifier', 'active']},
        ),
        migrations.RemoveField(
            model_name='bot',
            name='exchange',
        ),
    ]