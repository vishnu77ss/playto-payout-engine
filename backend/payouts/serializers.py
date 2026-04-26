from rest_framework import serializers
from .models import Merchant, BankAccount, Payout, LedgerEntry


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'created_at']


class BankAccountSerializer(serializers.ModelSerializer):
    masked_account = serializers.CharField(read_only=True)

    class Meta:
        model = BankAccount
        fields = [
            'id', 'account_holder_name', 'account_number',
            'masked_account', 'ifsc_code',
        ]


class PayoutSerializer(serializers.ModelSerializer):
    bank_account_masked = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            'id', 'merchant', 'bank_account', 'bank_account_masked',
            'amount_paise', 'status', 'failure_reason', 'attempt_count',
            'created_at', 'updated_at',
            'processing_started_at', 'completed_at',
        ]

    def get_bank_account_masked(self, obj):
        return obj.bank_account.masked_account()


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'amount_paise', 'entry_type',
            'description', 'payout', 'created_at',
        ]


class PayoutRequestSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.UUIDField()
