from functools import reduce
from math import ceil
from operator import itemgetter

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.forms import Select
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.template import Template, Context
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    DeleteView,
    UpdateView,
)

from overwatch.forms import ExchangeForm, AWSForm
from overwatch.models import Bot, BotError, BotPlacedOrder, BotTrade, Exchange, AWS


class ListBotView(LoginRequiredMixin, ListView):
    model = Bot

    def get_context_data(self, *args, object_list=None, **kwargs):
        context = super(ListBotView, self).get_context_data(*args, **kwargs)
        context["exchange_accounts"] = Exchange.objects.filter(owner=self.request.user)
        context["aws_accounts"] = AWS.objects.filter(owner=self.request.user)
        context["exchange_form"] = ExchangeForm()
        context["aws_form"] = AWSForm()
        return context


class DetailBotView(LoginRequiredMixin, DetailView):
    model = Bot


class UpdateBotView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = Bot
    fields = [
        "name",
        "exchange_account",
        "market",
        "use_market_price",
        "peg_currency",
        "peg_side",
        "aws_account",
        "tolerance",
        "fee",
        "bid_spread",
        "ask_spread",
        "order_amount",
        "total_bid",
        "total_ask",
        "base_price_url",
        "quote_price_url",
        "peg_price_url",
        "vigil_funds_alert_channel_id",
        "vigil_wrapper_error_channel_id",
        "schedule",
        "bot_type",
    ]

    def get_success_url(self):
        return reverse_lazy("bot_detail", kwargs={"pk": self.object.pk})

    def get_success_message(self, cleaned_data):
        return "{}@{} has been updated. Remember to Deploy or Update the Lambda function".format(
            self.object.name, self.object.exchange_account.exchange
        )

    def get_form(self, **kwargs):
        form = super(UpdateBotView, self).get_form(kwargs.get("form_class"))
        form.fields["market"].widget = Select()
        return form


class CreateBotView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Bot
    fields = [
        "name",
        "exchange_account",
        "market",
        "use_market_price",
        "peg_currency",
        "peg_side",
        "aws_account",
        "tolerance",
        "fee",
        "bid_spread",
        "ask_spread",
        "order_amount",
        "total_bid",
        "total_ask",
        "base_price_url",
        "quote_price_url",
        "peg_price_url",
        "owner",
        "vigil_funds_alert_channel_id",
        "vigil_wrapper_error_channel_id",
        "schedule",
        "bot_type",
    ]
    success_message = "%(name)s@%(exchange_account__exchange)s has been created. Remember to Deploy the Lambda function"
    success_url = reverse_lazy("index")

    def get_form(self, **kwargs):
        form = super(CreateBotView, self).get_form(kwargs.get("form_class"))
        form.fields["market"].widget = Select()
        return form


class DeleteBotView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = Bot
    success_message = "%(name)s has been deleted"
    success_url = reverse_lazy("index")


class DeployBotView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, pk):
        async_to_sync(get_channel_layer().send)(
            "bot-deploy", {"type": "deploy", "bot_pk": pk},
        )
        return redirect("bot_detail", pk=pk)


class DeactivateBotView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, pk):
        bot = get_object_or_404(Bot, pk=pk)
        bot.active = False
        bot.save()

        async_to_sync(get_channel_layer().send)(
            "bot-deploy", {"type": "deactivate", "bot_pk": pk},
        )
        return redirect("bot_detail", pk=pk)


class ActivateBotView(LoginRequiredMixin, View):
    @staticmethod
    def get(request, pk):
        bot = get_object_or_404(Bot, pk=pk)
        bot.active = True
        bot.save()

        async_to_sync(get_channel_layer().send)(
            "bot-deploy", {"type": "activate", "bot_pk": pk},
        )
        return redirect("bot_detail", pk=pk)


def generic_data_tables_view(request, object, bot_pk):
    # get the basic parameters
    draw = int(request.GET.get("draw", 0))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 0))

    # handle a search term
    search = request.GET.get("search[value]", "")
    query_set = object.objects.filter(bot__pk=bot_pk)
    results_total = query_set.count()

    if search:
        # start with a blank Q object and add a query for every non-relational field attached to the model
        q_objects = Q()

        for field in object._meta.fields:
            if field.is_relation:
                continue
            kwargs = {"{}__icontains".format(field.name): search}
            q_objects |= Q(**kwargs)

        query_set = query_set.filter(q_objects)

    # handle the ordering
    order_column_index = request.GET.get("order[0][column]")
    order_by = request.GET.get("columns[{}][name]".format(order_column_index))
    order_direction = request.GET.get("order[0][dir]")

    if order_direction == "desc":
        order_by = "-{}".format(order_by)

    if order_by:
        query_set = query_set.order_by(order_by)

    # now we have our completed queryset. we can paginate it
    index = start + 1  # start is 0 based, pages are 1 based
    page = Paginator(query_set, length).get_page(ceil(index / length))

    return {
        "draw": draw,
        "recordsTotal": results_total,
        "recordsFiltered": query_set.count(),
        "data": page,
    }


class BotErrorsDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotError, pk)
        return JsonResponse(
            {
                "draw": data["draw"],
                "recordsTotal": data["recordsTotal"],
                "recordsFiltered": data["recordsFiltered"],
                "data": [
                    [
                        Template("{{ error.time }}").render(Context({"error": error})),
                        error.title,
                        Template("{{ error.message | escape }}").render(
                            Context({"error": error})
                        ),
                    ]
                    for error in data["data"]
                ],
            }
        )


class BotPlacedOrdersDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotPlacedOrder, pk)
        return JsonResponse(
            {
                "draw": data["draw"],
                "recordsTotal": data["recordsTotal"],
                "recordsFiltered": data["recordsFiltered"],
                "data": [
                    [
                        Template("{{ placed_order.time }}").render(
                            Context({"placed_order": placed_order})
                        ),
                        placed_order.order_type,
                        round(placed_order.price, 8),
                        round(placed_order.price_usd, 8)
                        if placed_order.price_usd
                        else "Calculating",
                        placed_order.amount,
                    ]
                    for placed_order in data["data"]
                ],
            }
        )


class BotTradesDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotTrade, pk)
        return JsonResponse(
            {
                "draw": data["draw"],
                "recordsTotal": data["recordsTotal"],
                "recordsFiltered": data["recordsFiltered"],
                "data": [
                    [
                        Template("{{ trade.time }}").render(Context({"trade": trade})),
                        trade.trade_id,
                        trade.trade_type.title(),
                        round(trade.target_price_usd, 8)
                        if trade.target_price_usd
                        else "Calculating",
                        round(trade.trade_price_usd, 8)
                        if trade.trade_price_usd
                        else "Calculating",
                        trade.total,
                        round(trade.profit_usd, 2)
                        if trade.profit_usd
                        else "Calculating",
                    ]
                    for trade in data["data"]
                ],
            }
        )
