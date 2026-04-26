"""
Celery tasks for the payout pipeline.

  process_payout      : pending -> processing -> completed/failed
  retry_settlement    : retries the bank call for a payout already in
                        processing (used by the sweep)
  retry_stuck_payouts : periodic sweep for payouts stuck >30s in processing
  cleanup_expired_idempotency_keys : periodic GC
"""
import random
import time
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .exceptions import InvalidStateTransition
from .models import Payout
from .state_machine import transition_payout

logger = logging.getLogger(__name__)


# Tunable: bank simulation
SUCCESS_RATE = 0.70    # 70% complete cleanly
FAIL_RATE = 0.20       # 20% bank rejects
# Remaining 10% "hang" — payout stays in processing until the sweep retries.

MAX_ATTEMPTS = 3
STUCK_AFTER_SECONDS = 30


def _simulate_bank_settlement():
    """Simulate calling a slow flaky bank. Returns 'completed' | 'failed' | 'hung'."""
    time.sleep(random.uniform(0.5, 2.0))
    r = random.random()
    if r < SUCCESS_RATE:
        return 'completed'
    if r < SUCCESS_RATE + FAIL_RATE:
        return 'failed'
    return 'hung'


@shared_task
def process_payout(payout_id):
    """Initial pass: pending -> processing, then attempt settlement."""
    try:
        transition_payout(payout_id, Payout.Status.PROCESSING)
    except InvalidStateTransition as e:
        logger.warning("process_payout skipped: %s", e)
        return f'skipped: {e}'
    except Payout.DoesNotExist:
        return 'not found'

    outcome = _simulate_bank_settlement()
    return _resolve_outcome(payout_id, outcome)


@shared_task
def retry_settlement(payout_id):
    """Re-run the bank simulation for a payout already in PROCESSING."""
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        return 'not found'

    if payout.status != Payout.Status.PROCESSING:
        return f'skipped (status={payout.status})'

    outcome = _simulate_bank_settlement()
    return _resolve_outcome(payout_id, outcome, on_retry=True)


def _resolve_outcome(payout_id, outcome, *, on_retry=False):
    if outcome == 'completed':
        try:
            transition_payout(payout_id, Payout.Status.COMPLETED)
        except InvalidStateTransition as e:
            logger.warning("complete blocked: %s", e)
        return 'completed'

    if outcome == 'failed':
        reason = (
            'simulated bank rejection on retry'
            if on_retry else 'simulated bank rejection'
        )
        try:
            transition_payout(payout_id, Payout.Status.FAILED, failure_reason=reason)
        except InvalidStateTransition as e:
            logger.warning("fail blocked: %s", e)
        return 'failed'

    return 'hung'


@shared_task
def retry_stuck_payouts():
    """
    Periodic sweep. For every payout sitting in PROCESSING for more than
    STUCK_AFTER_SECONDS:
      - Increment attempt_count under a row lock (so two sweeps can't
        double-count the same payout)
      - If attempts >= MAX_ATTEMPTS, force-fail with a refund
      - Otherwise schedule retry_settlement with exponential backoff
    """
    cutoff = timezone.now() - timedelta(seconds=STUCK_AFTER_SECONDS)
    candidate_ids = list(
        Payout.objects
        .filter(
            status=Payout.Status.PROCESSING,
            processing_started_at__lt=cutoff,
        )
        .values_list('id', flat=True)
    )

    for payout_id in candidate_ids:
        with transaction.atomic():
            payout = (
                Payout.objects.select_for_update().get(id=payout_id)
            )
            # Re-check under the lock — another sweep may have just
            # advanced this payout.
            if payout.status != Payout.Status.PROCESSING:
                continue
            if payout.processing_started_at and \
               payout.processing_started_at >= cutoff:
                continue

            payout.attempt_count += 1
            payout.processing_started_at = timezone.now()
            payout.save(update_fields=['attempt_count', 'processing_started_at'])
            attempts = payout.attempt_count

        if attempts >= MAX_ATTEMPTS:
            try:
                transition_payout(
                    str(payout_id),
                    Payout.Status.FAILED,
                    failure_reason=(
                        f'max retries exceeded ({MAX_ATTEMPTS}); '
                        f'funds refunded'
                    ),
                )
            except InvalidStateTransition:
                pass
            continue

        # Exponential backoff: 2^attempts seconds (2, 4, 8, ...)
        countdown = 2 ** attempts
        retry_settlement.apply_async(
            args=[str(payout_id)], countdown=countdown
        )


@shared_task
def cleanup_expired_idempotency_keys():
    from .services import cleanup_expired_idempotency_keys as _cleanup
    return _cleanup()
