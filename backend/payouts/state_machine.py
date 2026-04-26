"""
The Payout state machine.

Allowed transitions are encoded once, here, and every status change goes
through transition_payout(). Anything not in ALLOWED_TRANSITIONS is rejected.

This is what makes "completed -> pending" or "failed -> completed"
illegal: the table doesn't list those moves, so they raise.
"""
from django.db import transaction
from django.utils import timezone

from .models import Payout, LedgerEntry
from .exceptions import InvalidStateTransition


# Map of current_status -> set of legal next statuses.
# Terminal states (completed, failed) map to an empty set.
ALLOWED_TRANSITIONS = {
    Payout.Status.PENDING: {
        Payout.Status.PROCESSING,
        Payout.Status.FAILED,
    },
    Payout.Status.PROCESSING: {
        Payout.Status.COMPLETED,
        Payout.Status.FAILED,
    },
    Payout.Status.COMPLETED: set(),
    Payout.Status.FAILED: set(),
}


def transition_payout(payout_id, new_status, failure_reason=None):
    """
    Atomically transition a payout to a new state.

    Locks the payout row first (SELECT FOR UPDATE) so two workers can't
    both flip the same payout. If new_status is FAILED, a REVERSAL ledger
    entry is created in the same transaction so the merchant always gets
    their held funds back together with the state change — not after.
    """
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)

        if new_status not in ALLOWED_TRANSITIONS[payout.status]:
            raise InvalidStateTransition(
                f"Illegal transition {payout.status} -> {new_status} "
                f"for payout {payout_id}"
            )

        payout.status = new_status

        if new_status == Payout.Status.PROCESSING:
            if payout.processing_started_at is None:
                payout.processing_started_at = timezone.now()

        elif new_status == Payout.Status.COMPLETED:
            payout.completed_at = timezone.now()

        elif new_status == Payout.Status.FAILED:
            payout.failure_reason = failure_reason or 'unknown'
            # Refund held funds atomically with the state transition.
            # Same DB transaction => either both happen or neither.
            LedgerEntry.objects.create(
                merchant_id=payout.merchant_id,
                amount_paise=payout.amount_paise,  # positive: refund
                entry_type=LedgerEntry.EntryType.REVERSAL,
                payout=payout,
                description=f"Reversal for failed payout {payout.id}",
            )

        payout.save()
        return payout
