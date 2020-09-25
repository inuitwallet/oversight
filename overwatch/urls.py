"""overwatch URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.views.decorators.http import require_POST, require_GET

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.ListBotView.as_view(), name="index"),
    # Bot urls
    path("bot/<int:pk>", views.DetailBotView.as_view(), name="bot_detail"),
    path("bot/create", views.CreateBotView.as_view(), name="bot_create"),
    path("bot/<int:pk>/edit", views.UpdateBotView.as_view(), name="bot_update"),
    path("bot/<int:pk>/delete", views.DeleteBotView.as_view(), name="bot_delete"),
    path("bot/config", views.BotApiConfigView.as_view(), name="bot_config"),
    # incoming data
    path(
        "bot/report_error",
        views.BotUserApiErrorsView.as_view(),
        name="bot_report_error",
    ),
    path(
        "bot/placed_order",
        views.BotApiPlacedOrderView.as_view(),
        name="bot_placed_order",
    ),
    path("bot/prices", views.BotApiPricesView.as_view(), name="bot_prices"),
    path("bot/balances", views.BotApiBalancesView.as_view(), name="bot_balance"),
    path("bot/trades", views.BotApiTradeView.as_view(), name="bot_trade"),
    # Display DataTables
    path(
        "bot/<int:pk>/error/datatables",
        views.BotErrorsDataTablesView.as_view(),
        name="bot_error_datatables",
    ),
    path(
        "bot/<int:pk>/placed_orders/datatables",
        views.BotPlacedOrdersDataTablesView.as_view(),
        name="bot_placed_orders_datatables",
    ),
    path(
        "bot/<int:pk>/trades/datatables",
        views.BotTradesDataTablesView.as_view(),
        name="bot_trades_datatables",
    ),
    path("bot/<int:pk>/deploy", views.DeployBotView.as_view(), name="deploy_bot"),
    path(
        "bot/<int:pk>/deactivate",
        views.DeactivateBotView.as_view(),
        name="deactivate_bot",
    ),
    path("bot/<int:pk>/activate", views.ActivateBotView.as_view(), name="activate_bot"),
    path(
        "account/aws/create",
        require_POST(views.AWSAccount.as_view()),
        name="aws_account_create",
    ),
    path(
        "account/aws/delete/<int:pk>",
        require_GET(views.AWSAccount.as_view()),
        name="aws_account_delete",
    ),
    path(
        "account/exchange/create",
        require_POST(views.ExchangeAccount.as_view()),
        name="exchange_account_create",
    ),
    path(
        "account/exchange/delete/<int:pk>",
        require_GET(views.ExchangeAccount.as_view()),
        name="exchange_account_delete",
    ),  # noqa
]
