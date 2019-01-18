import datetime
from math import ceil

import pygal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.template import Template, Context
from django.urls import reverse_lazy
from django.utils.timezone import now
from pygal.style import CleanStyle
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, DeleteView, UpdateView

from overwatch.models import Bot, BotError, BotPlacedOrder, BotTrade


class ListBotView(LoginRequiredMixin, ListView):
    model = Bot


class DetailBotView(LoginRequiredMixin, DetailView):
    model = Bot

    def get_placed_orders_chart(self):
        bid_points = []
        ask_points = []

        placed_orders = BotPlacedOrder.objects.filter(
            bot__pk=self.kwargs['pk'],
            time__gte=now() - datetime.timedelta(hours=48)
        ).order_by(
            'time'
        )

        for order in placed_orders:
            if order.order_type == 'sell':
                bid_points.append((order.time, None))
                ask_points.append((order.time, order.price))

            if order.order_type == 'buy':
                bid_points.append((order.time, order.price))
                ask_points.append((order.time, None))

        datetimeline = pygal.DateTimeLine(
            x_label_rotation=35,
            x_title='Date',
            y_title='Price',
            truncate_label=-1,
            legend_at_bottom=True,
            value_formatter=lambda x: '{:.8f}'.format(x),
            x_value_formatter=lambda dt: dt.strftime('%Y-%m-%d %H:%M:%S'),
            fill=True,
            style=CleanStyle(
                font_family='googlefont:Raleway',
            ),
        )
        datetimeline.add("Buy", bid_points, dots_size=2)
        datetimeline.add("Sell", ask_points, dots_size=2)
        return datetimeline.render_data_uri()

    def get_trades_chart(self):
        trades = BotTrade.objects.filter(
            bot__pk=self.kwargs['pk'],
            time__gte=now() - datetime.timedelta(days=60),
            profit_usd__isnull=False,
            bot_trade=True
        )

        line_chart = pygal.Bar(
            x_title='Days',
            y_title='Value in USD',
            legend_at_bottom=True,
            style=CleanStyle(
                font_family='googlefont:Raleway',
                value_font_size=10
            ),
            dynamic_print_values=True,
        )
        line_chart.value_formatter = lambda x: "$%.2f USD" % x
        line_chart.title = 'Aggregated profits over time'
        days = [30, 14, 7, 3, 2, 1]
        line_chart.x_labels = days
        profits = {'buy': [], 'sell': []}

        for day in days:
            for side in ['buy', 'sell']:
                profits[side].append(
                    trades.filter(
                        trade_type=side, time__gte=now() - datetime.timedelta(days=day)
                    ).aggregate(
                        profit=Sum('profit_usd')
                    )['profit']
                )

        line_chart.add('Buy', profits['buy'])
        line_chart.add('Sell', profits['sell'])
        line_chart.add(
            'Total',
            [float(buy or 0) + float(sell or 0) for buy, sell in zip(profits['buy'], profits['sell'])]
        )
        return line_chart.render_data_uri()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['placed_orders_chart'] = self.get_placed_orders_chart()
        context['trades_chart'] = self.get_trades_chart()
        context['last_balance'] = self.object.botbalance_set.first()

        context['peg'] = self.object.peg

        if self.object.peg.upper() == 'USNBT':
            context['peg'] = 'USD'

        if self.object.peg.upper() == 'CNNBT':
            context['peg'] = 'CNY'

        if self.object.peg.upper() == 'EUNBT':
            context['peg'] = 'EUR'

        return context


class UpdateBotView(SuccessMessageMixin, LoginRequiredMixin, UpdateView):
    model = Bot
    fields = ['name', 'exchange', 'base', 'quote', 'track', 'peg',
              'tolerance', 'fee', 'bid_spread', 'ask_spread', 'order_amount', 'total_bid', 'total_ask',
              'logs_group', 'aws_access_key', 'aws_secret_key']
    success_message = '%(name)s@%(exchange)s has been updated'

    def get_success_url(self):
        return reverse_lazy('bot_detail', kwargs={'pk': self.object.pk})


class CreateBotView(SuccessMessageMixin, LoginRequiredMixin, CreateView):
    model = Bot
    fields = ['name', 'exchange', 'base', 'quote', 'track', 'peg',
              'tolerance', 'fee', 'bid_spread', 'ask_spread', 'order_amount', 'total_bid', 'total_ask',
              'logs_group', 'aws_access_key', 'aws_secret_key']
    success_message = '%(name)s@%(exchange)s has been created'
    success_url = reverse_lazy('index')


class DeleteBotView(SuccessMessageMixin, LoginRequiredMixin, DeleteView):
    model = Bot
    success_message = '%(name)s has been deleted'
    success_url = reverse_lazy('index')


def generic_data_tables_view(request, object, bot_pk):
    # get the basic parameters
    draw = int(request.GET.get('draw', 0))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 0))

    # handle a search term
    search = request.GET.get('search[value]', '')
    query_set = object.objects.filter(bot__pk=bot_pk)
    results_total = query_set.count()

    if search:
        # start with a blank Q object and add a query for every non-relational field attached to the model
        q_objects = Q()

        for field in object._meta.fields:
            if field.is_relation:
                continue
            kwargs = {'{}__icontains'.format(field.name): search}
            q_objects |= Q(**kwargs)

        query_set = query_set.filter(q_objects)

    # handle the ordering
    order_column_index = request.GET.get('order[0][column]')
    order_by = request.GET.get('columns[{}][name]'.format(order_column_index))
    order_direction = request.GET.get('order[0][dir]')

    if order_direction == 'desc':
        order_by = '-{}'.format(order_by)

    if order_by:
        query_set = query_set.order_by(order_by)

    # now we have our completed queryset. we can paginate it
    index = start + 1  # start is 0 based, pages are 1 based
    page = Paginator(
        query_set,
        length
    ).get_page(
        ceil(index / length)
    )

    return {
        'draw': draw,
        'recordsTotal': results_total,
        'recordsFiltered': query_set.count(),
        'data': page
    }


class BotErrorsDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotError, pk)
        return JsonResponse(
            {
                'draw': data['draw'],
                'recordsTotal': data['recordsTotal'],
                'recordsFiltered': data['recordsFiltered'],
                'data': [
                    [
                        Template(
                            '{{ error.time }}'
                        ).render(
                            Context({'error': error})
                        ),
                        error.title,
                        error.message
                    ] for error in data['data']
                ]
            }
        )


class BotPlacedOrdersDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotPlacedOrder, pk)
        return JsonResponse(
            {
                'draw': data['draw'],
                'recordsTotal': data['recordsTotal'],
                'recordsFiltered': data['recordsFiltered'],
                'data': [
                    [
                        placed_order.time,
                        placed_order.order_type,
                        placed_order.price,
                        placed_order.amount
                    ] for placed_order in data['data']
                ]
            }
        )


class BotTradesDataTablesView(LoginRequiredMixin, View):
    def get(self, request, pk):
        data = generic_data_tables_view(request, BotTrade, pk)
        return JsonResponse(
            {
                'draw': data['draw'],
                'recordsTotal': data['recordsTotal'],
                'recordsFiltered': data['recordsFiltered'],
                'data': [
                    [
                        trade.time,
                        trade.trade_id,
                        trade.trade_type.title(),
                        round(trade.target_price_usd, 8),
                        round(trade.trade_price_usd, 8),
                        trade.amount,
                        round(trade.profit_usd, 2)
                    ] for trade in data['data']
                ]
            }
        )
