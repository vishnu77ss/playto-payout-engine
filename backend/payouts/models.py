"""
Data models for the Playto Payout Engine.

Money is stored as BigIntegerField in paise (1 INR = 100 paise).
Float and Decimal are deliberately avoided here because every cent matters
and integer arithmetic at the database level is exact.
"""
import uuid
from django.db import models


class Merchant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BankAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, related_name='bank_accounts', on_delete=models.CASCADE
    )
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    account_holder_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def masked_account(self):
        return '****' + self.account_number[-4:]

    def __str__(self):
        return f"{self.account_holder_name} ({self.masked_account()})"


class Payout(models.Model):
    """
    A payout is a request to move money from a merchant's Playto balance
    to their Indian bank account. Lifecycle:

        pending -> processing -> completed
        pending -> processing -> failed     (held funds are refunded via REVERSAL)
        pending -> failed                   (rejected before sending to bank)
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, related_name='payouts', on_delete=models.PROTECT
    )
    bank_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT)
    amount_paise = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    failure_reason = models.TextField(blank=True, null=True)
    attempt_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['merchant', 'status']),
            models.Index(fields=['status', 'processing_started_at']),
            models.Index(fields=['merchant', '-created_at']),
        ]

    def __str__(self):
        return f"Payout {self.id} - {self.amount_paise}p - {self.status}"


class LedgerEntry(models.Model):
    """
    Append-only ledger of every money movement for a merchant.

    - CREDIT entries are positive and represent customer payments coming in.
    - DEBIT entries are negative and represent payouts going out.
    - REVERSAL entries are positive and refund a failed payout's debit.

    Available balance = SUM(amount_paise) for the merchant.
    Held balance      = abs(SUM(DEBIT amount_paise)) for payouts in
                        pending/processing.
    """
    class EntryType(models.TextChoices):
        CREDIT = 'credit', 'Credit'
        DEBIT = 'debit', 'Debit'
        REVERSAL = 'reversal', 'Reversal'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        Merchant, related_name='ledger_entries', on_delete=models.PROTECT
    )
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    payout = models.ForeignKey(
        Payout, null=True, blank=True, on_delete=models.PROTECT,
        related_name='ledger_entries',
    )
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['merchant', '-created_at']),
            models.Index(fields=['payout']),
        ]

    def __str__(self):
        return f"{self.entry_type} {self.amount_paise}p"


class IdempotencyKey(models.Model):
    """
    Stores client-supplied idempotency keys, scoped per merchant, so that
    duplicate POSTs return the original response instead of creating a
    second payout. Expires after IDEMPOTENCY_KEY_TTL_HOURS.
    """
    class Status(models.TextChoices):
        IN_FLIGHT = 'in_flight', 'In Flight'
        COMPLETED = 'completed', 'Completed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IN_FLIGHT
    )
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    payout = models.ForeignKey(
        Payout, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # The composite unique constraint is what makes idempotency atomic:
        # the second concurrent INSERT will raise IntegrityError instead of
        # silently creating a duplicate.
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'key'], name='uniq_merchant_idempotency_key'
            ),
        ]
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.key} ({self.status})"
