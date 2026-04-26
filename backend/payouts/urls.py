from django.urls import path
from . import views


urlpatterns = [
    path('merchants/', views.list_merchants),
    path('merchants/<uuid:merchant_id>/balance/', views.merchant_balance),
    path('merchants/<uuid:merchant_id>/ledger/', views.merchant_ledger),
    path('merchants/<uuid:merchant_id>/bank-accounts/', views.list_bank_accounts),
    path('merchants/<uuid:merchant_id>/payouts/', views.list_payouts),
    path('merchants/<uuid:merchant_id>/payouts/request/', views.request_payout),
]
