# Generated by Django 2.1.5 on 2019-11-10 19:53

from django.db import migrations
import encrypted_model_fields.fields


def resave_bots(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    Bot = apps.get_model("overwatch", "Bot")
    for bot in Bot.objects.all():
        bot.save()


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0033_auto_20191110_1939"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bot",
            name="aws_access_key",
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True, help_text="database encrypted", null=True
            ),
        ),
        migrations.AlterField(
            model_name="bot",
            name="aws_secret_key",
            field=encrypted_model_fields.fields.EncryptedCharField(
                blank=True,
                help_text="database encrypted and hidden from display",
                null=True,
            ),
        ),
        migrations.RunPython(resave_bots, resave_bots),
    ]
