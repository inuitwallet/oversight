import hashlib
import hmac
import uuid
from django.db import models


class Bot(models.Model):
    name = models.CharField(
        max_length=255,
    )
    exchange = models.CharField(
        max_length=255
    )
    base = models.CharField(
        max_length=255,
    )
    quote = models.CharField(
        max_length=255,
    )
    track = models.CharField(
        max_length=255,
    )
    peg = models.CharField(
        max_length=255,
    )
    tolerance = models.FloatField()
    fee = models.FloatField()
    order_amount = models.FloatField()
    total_bid = models.FloatField()
    total_ask = models.FloatField()
    api_secret = models.UUIDField(
        default=uuid.uuid4
    )
    last_nonce = models.BigIntegerField(
        default=0
    )

    def __str__(self):
        return self.name

    def serialize(self):
        return {
            'name': self.name,
            'exchange': self.exchange,
            'base': self.base,
            'quote': self.quote,
            'track': self.track,
            'peg': self.peg,
            'tolerance': self.tolerance,
            'fee': self.fee,
            'order_amount': self.order_amount,
            'total_bid': self.total_bid,
            'total_ask': self.total_ask
        }

    def auth(self, supplied_hash, name, exchange, nonce):
        # check that the supplied nonce is an integer
        # and is greater than the last supplied nonce to prevent reuse
        try:
            nonce = int(nonce)
        except ValueError:
            return False, 'n parameter needs to be a positive integer'

        if nonce <= self.last_nonce:
            return False, 'n parameter needs to be a positive integer and greater than the previous nonce'

        # calculate the hash from our own data
        calculated_hash = hmac.new(
            self.api_secret.bytes,
            '{}{}{}'.format(
                name.lower(),
                exchange.lower(),
                nonce
            ).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # update the last nonce value
        self.last_nonce = nonce
        self.save()

        if calculated_hash != supplied_hash:
            return False, 'supplied hash does not match calculated hash'

        return True, 'authenticated'

    @property
    def latest_heartbeat(self):
        latest_heartbeat = self.botheartbeat_set.first()
        if latest_heartbeat:
            return latest_heartbeat.time

        return ''


class BotHeartBeat(models.Model):
    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE
    )
    time = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return '{}'.format(self.time)

    class Meta:
        ordering = ['-time']
