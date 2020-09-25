import hashlib
import hmac
import uuid
import datetime

import pygal
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils.timezone import now
from pygal.style import CleanStyle

from overwatch.utils.price_aggregator import get_price_movement
from encrypted_model_fields.fields import EncryptedCharField


def no_slash(value):
    if "/" in value:
        raise ValidationError('Name cannot contain the "/" character')


class Bot(models.Model):
    # operational config options
    name = models.CharField(
        max_length=255,
        help_text="Name to identify this bot. Usually the name of the pair it operates on",
        validators=[no_slash],
    )
    exchange_account = models.ForeignKey(
        "Exchange",
        on_delete=models.SET_NULL,
        null=True,
        help_text="The exchange account to use",
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    active = models.BooleanField(default=True, db_index=True)
    market = models.CharField(
        max_length=255, help_text="The Market to operate on", choices=[]
    )
    use_market_price = models.BooleanField(default=False, db_index=True)
    peg_currency = models.CharField(
        max_length=255,
        blank=True,
        help_text="The currency to peg to. The value of this currency will be used to calculate the prices the bot uses",
    )
    peg_side = models.CharField(
        max_length=255,
        blank=True,
        help_text="Which side of the market pair the peg applies to",
        choices=[("base", "Base"), ("quote", "Quote")],
    )
    tolerance = models.FloatField(
        help_text="How far from the price an order can be before it is cancelled and replaced at the correct price."
        "Show as a Percentage"
    )
    fee = models.FloatField(
        help_text="The fee to apply to each side. Shown as a percentage"
    )
    bid_spread = models.FloatField(
        help_text="The spread to add to the fee on the Buy side"
    )
    ask_spread = models.FloatField(
        help_text="The spread to add to the fee on the Sell side"
    )
    order_amount = models.FloatField(
        help_text="The amount in USD that each order should be"
    )
    total_bid = models.FloatField(
        help_text="The total amount of funds allowed on the Buy side in USD"
    )
    total_ask = models.FloatField(
        help_text="The total amount of funds allowed on the Sell side in USD"
    )
    api_secret = models.UUIDField(default=uuid.uuid4)
    last_nonce = models.BigIntegerField(default=0)
    base_price_url = models.URLField(
        default="https://price-aggregator.crypto-daio.co.uk/price"
    )
    quote_price_url = models.URLField(
        default="https://price-aggregator.crypto-daio.co.uk/price"
    )
    peg_price_url = models.URLField(
        default="https://price-aggregator.crypto-daio.co.uk/price"
    )

    peg_decimal_places = models.IntegerField(default=6)
    base_decimal_places = models.IntegerField(default=6)
    quote_decimal_places = models.IntegerField(default=6)

    # deployment config options
    aws_account = models.ForeignKey(
        "AWS", on_delete=models.SET_NULL, null=True, help_text=""
    )
    bot_type = models.CharField(max_length=255, choices=settings.BOT_TYPES)
    logs_group = models.CharField(
        max_length=255,
        help_text="AWS Cloudwatch logs group name",
        blank=True,
        null=True,
    )
    sleep_long = models.IntegerField(default=5)
    sleep_medium = models.IntegerField(default=3)
    sleep_short = models.IntegerField(default=2)
    vigil_funds_alert_channel_id = EncryptedCharField(
        max_length=255,
        help_text="Use for reporting fund errors via Vigil.\nDatabase encrypted",
        blank=True,
        null=True,
    )
    vigil_wrapper_error_channel_id = EncryptedCharField(
        max_length=255,
        help_text="Use for reporting bot errors via Vigil.\nDatabase encrypted",
        blank=True,
        null=True,
    )
    timeout = models.IntegerField(default=300)
    schedule = models.IntegerField(
        default=2, help_text="How often the bot should run (Minutes)"
    )

    def __str__(self):
        return "{}{}".format(
            self.name,
            "@{}".format(self.exchange_account.exchange.title())
            if self.exchange_account
            else "",
        )

    class Meta:
        ordering = ["name", "exchange_account__identifier", "active"]

    def serialize(self):
        return {
            "name": self.name,
            "exchange": self.exchange_account.exchange,
            "market": self.market,
            "use_market_price": self.use_market_price,
            "peg_currency": self.peg_currency,
            "peg_side": self.peg_side,
            "tolerance": self.tolerance / 100,
            "fee": self.fee / 100,
            "bid_spread": self.bid_spread / 100,
            "ask_spread": self.ask_spread / 100,
            "order_amount": self.order_amount,
            "total_bid": self.total_bid,
            "total_ask": self.total_ask,
            "base_price_url": self.base_price_url,
            "quote_price_url": self.quote_price_url,
            "peg_price_url": self.peg_price_url,
        }

    def auth(self, supplied_hash, name, exchange, nonce):
        # check that the supplied nonce is an integer
        # and is greater than the last supplied nonce to prevent reuse
        try:
            nonce = int(nonce)
        except ValueError:
            return False, "n parameter needs to be a positive integer"

        if nonce <= self.last_nonce:
            return (
                False,
                "n parameter needs to be a positive integer and greater than the previous nonce",
            )

        # calculate the hash from our own data
        calculated_hash = hmac.new(
            self.api_secret.bytes,
            "{}{}{}".format(name.lower(), exchange.lower(), nonce).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # update the last nonce value
        self.last_nonce = nonce
        self.save()

        if calculated_hash != supplied_hash:
            return False, "supplied hash does not match calculated hash"

        return True, "authenticated"

    @property
    def base(self):
        return self.market.split("/")[0] if self.market else None

    @property
    def quote(self):
        return self.market.split("/")[1] if self.market else None

    @property
    def latest_heartbeat(self):
        latest_heartbeat = self.botheartbeat_set.first()

        if latest_heartbeat:
            return latest_heartbeat.time

        return ""

    @property
    def last_error(self):
        latest_error = self.boterror_set.first()

        if latest_error:
            return latest_error.time

        return ""

    @property
    def last_price(self):
        return self.botprice_set.exclude(price_usd__isnull=True).first()

    @property
    def last_balance(self):
        return self.botbalance_set.first()

    @property
    def spread(self):
        return max(self.last_price.bid_price, self.last_price.ask_price) - min(
            self.last_price.bid_price, self.last_price.ask_price
        )

    def rendered_price(self, usd=True):
        if usd:
            dp = str(4)
            template = (
                "{{ last_price.price_usd|floatformat:" + dp + " }} {{ currency }}"
            )
        else:
            dp = str(self.base_decimal_places)
            template = "{{ last_price.price|floatformat:" + dp + " }} {{ currency }}"

        return Template(template).render(
            Context(
                {
                    "last_price": self.last_price if self.last_price else 0,
                    "currency": ("USD" if usd else self.quote)
                    if self.last_price
                    else "",
                }
            )
        )

    def price_sparkline(self):
        prices = self.botprice_set.exclude(price_usd__isnull=True)[:30].values_list(
            "price", flat=True
        )

        chart = pygal.Line()
        chart.add("", list(prices))
        return chart.render_sparkline(is_unicode=True)

    def rendered_bid_price(self, usd=True):
        if usd:
            dp = str(4)
            template = (
                "{{ last_price.bid_price_usd|floatformat:" + dp + " }} {{ currency }}"
            )
        else:
            dp = str(self.base_decimal_places)
            template = (
                "{{ last_price.bid_price|floatformat:" + dp + " }} {{ currency }}"
            )

        return Template(template).render(
            Context(
                {
                    "last_price": self.last_price,
                    "currency": "USD" if usd else self.quote,
                }
            )
        )

    def rendered_ask_price(self, usd=True):
        if usd:
            dp = str(4)
            template = (
                "{{ last_price.ask_price_usd|floatformat:" + dp + " }} {{ currency }}"
            )
        else:
            dp = str(self.base_decimal_places)
            template = (
                "{{ last_price.ask_price|floatformat:" + dp + " }} {{ currency }}"
            )

        return Template(template).render(
            Context(
                {
                    "last_price": self.last_price,
                    "currency": "USD" if usd else self.quote,
                }
            )
        )

    def rendered_market_price(self, usd=True):
        if usd:
            dp = str(4)
            template = (
                "{{ last_price.market_price_usd|default:0.0|floatformat:"
                + dp
                + " }} {{ currency }}"
            )
        else:
            dp = str(self.base_decimal_places)
            template = (
                "{{ last_price.market_price|floatformat:" + dp + " }} {{ currency }}"
            )

        market_price_value = Template(template).render(
            Context(
                {
                    "last_price": self.last_price,
                    "currency": "USD" if usd else self.quote,
                }
            )
        )

        return render_to_string(
            "overwatch/fragments/bot_list/market-price.html",
            {
                "market_price": self.use_market_price,
                "market_price_value": market_price_value,
            },
        )

    def rendered_bid_balance(self, on_order=True, usd=True):
        if usd:
            dp = str(4)
            currency = "USD"
        else:
            dp = str(self.base_decimal_places)
            currency = self.base

        if on_order:
            if usd:
                template = (
                    "{{ last_balance.bid_on_order_usd|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
            else:
                template = (
                    "{{ last_balance.bid_on_order|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
        else:
            if usd:
                template = (
                    "{{ last_balance.bid_available_usd|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
            else:
                template = (
                    "{{ last_balance.bid_available_as_base|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )

        return Template(template).render(
            Context(
                {
                    "last_balance": self.last_balance if self.last_balance else 0,
                    "currency": currency,
                }
            )
        )

    def rendered_ask_balance(self, on_order=True, usd=True):
        if usd:
            dp = str(4)
            currency = "USD"
        else:
            dp = str(self.base_decimal_places)
            currency = self.base

        if on_order:
            if usd:
                template = (
                    "{{ last_balance.ask_on_order_usd|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
            else:
                template = (
                    "{{ last_balance.ask_on_order|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
        else:
            if usd:
                template = (
                    "{{ last_balance.ask_available_usd|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )
            else:
                template = (
                    "{{ last_balance.ask_available|floatformat:"
                    + dp
                    + " }} {{ currency }}"
                )

        return Template(template).render(
            Context(
                {
                    "last_balance": self.last_balance if self.last_balance else 0,
                    "currency": currency,
                }
            )
        )

    def profit(self, days=1):
        return float(
            self.bottrade_set.filter(
                time__gte=now() - datetime.timedelta(days=days),
                profit_usd__isnull=False,
                bot_trade=True,
            ).aggregate(profit=Sum("profit_usd"))["profit"]
            or 0.0
        )

    def rendered_profit(self, days=1):
        return render_to_string(
            "overwatch/fragments/bot_list/profit.html", {"profit": self.profit(days)}
        )

    def get_placed_orders_chart(self, hours=48):
        bid_points = []
        ask_points = []

        placed_orders = (
            self.botplacedorder_set.filter(
                time__gte=now() - datetime.timedelta(hours=hours)
            )
            .exclude(price_usd__isnull=True)
            .order_by("time")
        )

        for order in placed_orders:
            if order.order_type == "sell":
                ask_points.append((order.time, order.price_usd))

            if order.order_type == "buy":
                bid_points.append((order.time, order.price_usd))

        datetimeline = pygal.DateTimeLine(
            x_label_rotation=35,
            x_title="Date",
            y_title="Price (USD)",
            truncate_label=-1,
            legend_at_bottom=True,
            value_formatter=lambda x: "${:.8f}".format(x),
            x_value_formatter=lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S"),
            style=CleanStyle(font_family="googlefont:Raleway",),
        )
        datetimeline.add("Buy", bid_points, dots_size=2)
        datetimeline.add("Sell", ask_points, dots_size=2)
        return datetimeline.render_data_uri()

    def get_trades_chart(self, days=None):
        trades = self.bottrade_set.filter(
            time__gte=now() - datetime.timedelta(days=60),
            profit_usd__isnull=False,
            bot_trade=True,
        )

        chart = pygal.StackedBar(
            x_title="Days",
            y_title="Value in USD",
            legend_at_bottom=True,
            style=CleanStyle(font_family="googlefont:Raleway", value_font_size=10),
            dynamic_print_values=True,
        )
        chart.value_formatter = lambda x: "$%.2f USD" % x
        chart.title = "Aggregated profits over time"

        if days is None:
            days = [1, 3, 7, 14, 30]

        chart.x_labels = days
        profits = {"buy": [], "sell": []}

        if not self.base:
            return chart.render_data_uri()

        movements = get_price_movement(self.base_price_url, self.base)

        for side in ["buy", "sell"]:
            running_total = 0
            previous_day = 0

            for day in days:
                profit = trades.filter(
                    trade_type=side,
                    time__lt=now() - datetime.timedelta(days=previous_day),
                    time__gte=now() - datetime.timedelta(days=day),
                ).aggregate(profit=Sum("profit_usd"))["profit"]

                movement_factor = 1

                if movements:
                    movement_factor = (
                        movements.get("number_of_days", {})
                        .get(str(day), {})
                        .get("movement_factor", 1)
                    )

                if profit:
                    adjusted_profit = profit * movement_factor
                else:
                    adjusted_profit = 0

                running_total += adjusted_profit
                profits[side].append(running_total)

                previous_day = day

        chart.add("Buy", profits["buy"])
        chart.add("Sell", profits["sell"])
        return chart.render_data_uri()

    def get_balances_chart(self):
        balances = self.botbalance_set.filter(
            time__gte=now() - datetime.timedelta(days=30),
        ).order_by("time")

        bid_balances = []
        ask_balances = []

        earliest = balances.first()

        if earliest is None:
            return ""

        bid_balances.append(earliest.bid_available_usd + earliest.bid_on_order_usd)
        ask_balances.append(earliest.ask_available_usd + earliest.ask_on_order_usd)

        next_time = earliest.time + datetime.timedelta(hours=6)

        for balance in balances:
            if balance.time < next_time:
                continue

            all_attributes = True

            for attribute in [
                balance.bid_available_usd,
                balance.bid_on_order_usd,
                balance.ask_available_usd,
                balance.ask_on_order_usd,
            ]:
                if attribute is None:
                    balance.updated = False
                    balance.save()
                    all_attributes = False

            if not all_attributes:
                continue

            bid_balances.append(balance.bid_available_usd + balance.bid_on_order_usd)
            ask_balances.append(balance.ask_available_usd + balance.ask_on_order_usd)
            next_time = next_time + datetime.timedelta(hours=6)

        line = pygal.Line(
            y_title="Amount in USD",
            truncate_label=-1,
            legend_at_bottom=True,
            value_formatter=lambda value: "USD {:.4f}".format(value),
            style=CleanStyle(font_family="googlefont:Raleway",),
        )
        line.add("Bid Available", bid_balances, stroke_style={"width": 5}, dot_size=1)
        line.add("Ask Available", ask_balances, stroke_style={"width": 5}, dot_size=1)
        return line.render_data_uri()
