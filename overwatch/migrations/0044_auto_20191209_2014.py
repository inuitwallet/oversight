# Generated by Django 2.1.5 on 2019-12-09 20:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0043_auto_20191209_1234"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bot",
            name="peg_currency",
            field=models.CharField(
                blank=True,
                help_text="The currency to peg to. The value of this currency will be used to calculate the prices the bot uses",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="bot",
            name="peg_side",
            field=models.CharField(
                blank=True,
                choices=[("base", "Base"), ("quote", "Quote")],
                help_text="Which side of the market pair the peg applies to",
                max_length=255,
            ),
        ),
    ]
