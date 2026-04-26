from django.contrib import admin
from .models import Merchant, BankAccount, Payout, LedgerEntry, IdempotencyKey


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'created_at')


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('account_holder_name', 'merchant', 'masked_account', 'ifsc_code')


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'amount_paise', 'status', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'merchant', 'amount_paise', 'entry_type', 'created_at')
    list_filter = ('entry_type',)


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ('key', 'merchant', 'status', 'response_status_code', 'created_at')
    list_filter = ('status',)
