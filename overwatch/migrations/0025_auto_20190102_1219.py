# Generated by Django 2.1 on 2019-01-02 12:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0024_auto_20190102_1152"),
    ]

    operations = [
        migrations.AddField(
            model_name="botplacedorder",
            name="price_usd",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="botplacedorder",
            name="updated",
            field=models.BooleanField(default=False),
        ),
    ]
