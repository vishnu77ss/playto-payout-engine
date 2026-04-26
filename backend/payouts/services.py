"""
Business logic for payouts.

Two functions matter most here:
  - get_balance_breakdown: derives available/held balances from the ledger
  - create_payout: the full atomic flow with locking + idempotency
"""
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from .exceptions import (
    BankAccountNotFound,
    IdempotencyConflict,
    IdempotencyInFlight,
)
from .models import BankAccount, IdempotencyKey, LedgerEntry, Merchant, Payout


# ---------------------------------------------------------------------------
# Balance
# ---------------------------------------------------------------------------

def get_balance_breakdown(merchant_id):
    """
    Returns the merchant's balance, computed at the database level.
    Never sums in Python — that would mean fetching every row over the wire
    and is a classic source of off-by-one and rounding bugs.
    """
    available = LedgerEntry.objects.filter(
        merchant_id=merchant_id
    ).aggregate(total=Sum('amount_paise'))['total'] or 0

    # Held = abs(sum of DEBIT entries whose payout is still in flight)
    held_negative = LedgerEntry.objects.filter(
        merchant_id=merchant_id,
        entry_type=LedgerEntry.EntryType.DEBIT,
        payout__status__in=[
            Payout.Status.PENDING,
            Payout.Status.PROCESSING,
        ],
    ).aggregate(total=Sum('amount_paise'))['total'] or 0
    held = abs(held_negative)

    return {
        'available_paise': available,
        'held_paise': held,
        'total_paise': available + held,
    }


# ---------------------------------------------------------------------------
# Idempotency helpers
# ---------------------------------------------------------------------------

def _hash_request(body):
    """Stable hash of a request body so we can detect key reuse with a
    different payload (which is a client bug, not idempotency)."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode()
    ).hexdigest()


# ---------------------------------------------------------------------------
# Create payout — the main flow
# ---------------------------------------------------------------------------

def create_payout(*, merchant_id, amount_paise, bank_account_id,
                  idempotency_key, request_body):
    """
    Create a payout request. Returns a dict:

        {'replayed': bool, 'status_code': int, 'body': dict}

    Steps:
      1.  Try to insert the idempotency row. INSERT racing on a unique
          constraint is the cheapest cross-process lock there is.
      2.  If a previous request with the same key already finished,
          return its stored response verbatim.
      3.  Otherwise, lock the merchant row (SELECT FOR UPDATE) so two
          payout requests for the same merchant cannot both pass the
          balance check.
      4.  Compute available balance at the DB level, reject if too low.
      5.  Create the Payout row + the DEBIT ledger entry in the same
          transaction. The negative DEBIT immediately reduces available
          balance; concurrent requests waiting on the lock will see it.
      6.  Mark the idempotency row COMPLETED with the response.
      7.  After commit, dispatch the Celery task that will move the
          payout through processing.
    """
    request_hash = _hash_request(request_body)

    # Step 1 + 2: idempotency
    try:
        # Open the transaction *outside* this insert so a failed conflict
        # doesn't poison the rest of the work.
        with transaction.atomic():
            idem = IdempotencyKey.objects.create(
                merchant_id=merchant_id,
                key=idempotency_key,
                request_hash=request_hash,
                status=IdempotencyKey.Status.IN_FLIGHT,
            )
    except IntegrityError:
        existing = IdempotencyKey.objects.get(
            merchant_id=merchant_id, key=idempotency_key
        )
        if existing.request_hash != request_hash:
            raise IdempotencyConflict(
                "Idempotency-Key was reused with a different request body."
            )
        if existing.status == IdempotencyKey.Status.IN_FLIGHT:
            # First request hasn't finished yet. Tell the client to retry.
            raise IdempotencyInFlight(
                "Original request is still being processed. Try again shortly."
            )
        # Replayed completed request — return the stored response as-is.
        return {
            'replayed': True,
            'status_code': existing.response_status_code,
            'body': existing.response_body,
        }

    # Steps 3–6 in one DB transaction.
    try:
        with transaction.atomic():
            # Lock merchant. Anyone else wanting this row blocks here.
            merchant = (
                Merchant.objects
                .select_for_update()
                .get(id=merchant_id)
            )

            try:
                bank_account = BankAccount.objects.get(
                    id=bank_account_id, merchant_id=merchant_id
                )
            except BankAccount.DoesNotExist:
                raise BankAccountNotFound(
                    "Bank account not found for this merchant."
                )

            balance = get_balance_breakdown(merchant_id)
            if amount_paise > balance['available_paise']:
                response_body = {
                    'error': 'insufficient_balance',
                    'available_paise': balance['available_paise'],
                    'requested_paise': amount_paise,
                }
                idem.status = IdempotencyKey.Status.COMPLETED
                idem.response_status_code = 422
                idem.response_body = response_body
                idem.save()
                return {
                    'replayed': False,
                    'status_code': 422,
                    'body': response_body,
                }

            payout = Payout.objects.create(
                merchant=merchant,
                bank_account=bank_account,
                amount_paise=amount_paise,
                status=Payout.Status.PENDING,
            )

            # DEBIT immediately. This is what holds the funds — once this
            # row exists, get_balance_breakdown() will exclude this amount
            # from the next request's available balance.
            LedgerEntry.objects.create(
                merchant=merchant,
                amount_paise=-amount_paise,
                entry_type=LedgerEntry.EntryType.DEBIT,
                payout=payout,
                description=f"Payout {payout.id}",
            )

            response_body = {
                'id': str(payout.id),
                'merchant_id': str(merchant_id),
                'bank_account_id': str(bank_account_id),
                'amount_paise': amount_paise,
                'status': payout.status,
                'created_at': payout.created_at.isoformat(),
            }
            idem.status = IdempotencyKey.Status.COMPLETED
            idem.response_status_code = 201
            idem.response_body = response_body
            idem.payout = payout
            idem.save()

            # Step 7: dispatch only after the transaction has committed.
            # If we dispatched inside the transaction the worker could
            # pick up the payout before our INSERT is visible.
            from .tasks import process_payout
            transaction.on_commit(
                lambda: process_payout.delay(str(payout.id))
            )

            return {
                'replayed': False,
                'status_code': 201,
                'body': response_body,
            }
    except Exception:
        # Anything goes wrong post-idempotency-insert: release the key so
        # the client can retry without being told "request in flight".
        IdempotencyKey.objects.filter(pk=idem.pk).delete()
        raise


# ---------------------------------------------------------------------------
# Idempotency key cleanup (called from a Celery beat task)
# ---------------------------------------------------------------------------

def cleanup_expired_idempotency_keys():
    cutoff = timezone.now() - timedelta(
        hours=settings.IDEMPOTENCY_KEY_TTL_HOURS
    )
    deleted, _ = IdempotencyKey.objects.filter(created_at__lt=cutoff).delete()
    return deleted
