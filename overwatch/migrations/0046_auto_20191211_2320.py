# Generated by Django 2.1.5 on 2019-12-11 23:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("overwatch", "0045_bot_peg_price_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bot",
            name="order_amount",
            field=models.FloatField(
                help_text="The amount in USD that each order should be"
            ),
        ),
        migrations.AlterField(
            model_name="bot",
            name="total_ask",
            field=models.FloatField(
                help_text="The total amount of funds allowed on the Sell side in USD"
            ),
        ),
        migrations.AlterField(
            model_name="bot",
            name="total_bid",
            field=models.FloatField(
                help_text="The total amount of funds allowed on the Buy side in USD"
            ),
        ),
    ]
