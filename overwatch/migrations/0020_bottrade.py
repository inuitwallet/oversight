# Generated by Django 2.1 on 2018-10-29 20:26

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0019_auto_20181006_1933"),
    ]

    operations = [
        migrations.CreateModel(
            name="BotTrade",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("time", models.DateTimeField(default=django.utils.timezone.now)),
                ("trade_id", models.CharField(max_length=255)),
                ("trade_type", models.CharField(max_length=255)),
                ("price", models.FloatField()),
                ("amount", models.FloatField()),
                ("total", models.FloatField()),
                ("age", models.DurationField(blank=True, null=True)),
                ("target_price_usd", models.FloatField(blank=True, null=True)),
                ("trade_price_usd", models.FloatField(blank=True, null=True)),
                ("difference_usd", models.FloatField(blank=True, null=True)),
                ("profit_usd", models.FloatField(blank=True, null=True)),
                (
                    "bot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="overwatch.Bot"
                    ),
                ),
            ],
        ),
    ]
