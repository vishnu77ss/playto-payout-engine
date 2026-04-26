"""
Concurrency test: two threads submit a payout for the same merchant at
the same time. The merchant's available balance only allows ONE of them
to succeed. The other must be rejected with insufficient_balance.

This is the test that proves the SELECT FOR UPDATE lock works. If the
balance check were a normal Python `if balance >= amount`, both threads
would observe the same balance and both would succeed — overdrawing the
merchant.
"""
import threading
import uuid

from django.db import connection
from django.test import TransactionTestCase

from payouts.models import (
    BankAccount, LedgerEntry, Merchant, Payout,
)
from payouts.services import create_payout, get_balance_breakdown


class ConcurrencyTest(TransactionTestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Concurrent Co', email='c@x.com'
        )
        self.bank = BankAccount.objects.create(
            merchant=self.merchant,
            account_number='100200300400',
            ifsc_code='HDFC0000001',
            account_holder_name='Concurrent Co',
        )
        # Seed exactly ₹100 = 10000 paise
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=10_000,
            entry_type=LedgerEntry.EntryType.CREDIT,
            description='seed credit',
        )

    def test_two_simultaneous_payouts_only_one_succeeds(self):
        """Each thread requests ₹60 against a ₹100 balance.
        Exactly one payout row should exist and the other request must
        return 422 insufficient_balance."""
        results = []
        results_lock = threading.Lock()

        def submit():
            try:
                r = create_payout(
                    merchant_id=str(self.merchant.id),
                    amount_paise=6_000,
                    bank_account_id=str(self.bank.id),
                    idempotency_key=str(uuid.uuid4()),
                    request_body={
                        'amount_paise': 6_000,
                        'bank_account_id': str(self.bank.id),
                    },
                )
                with results_lock:
                    results.append(r)
            finally:
                # Threads in Django tests must close their own DB connection
                connection.close()

        t1 = threading.Thread(target=submit)
        t2 = threading.Thread(target=submit)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        success = [r for r in results if r['status_code'] == 201]
        rejected = [r for r in results if r['status_code'] == 422]

        self.assertEqual(len(success), 1,
                         f'Expected 1 success, got {len(success)}: {results}')
        self.assertEqual(len(rejected), 1,
                         f'Expected 1 rejection, got {len(rejected)}')

        # Exactly one Payout row created.
        self.assertEqual(
            Payout.objects.filter(merchant=self.merchant).count(), 1,
        )

        # Balance integrity: 100 - 60 = 40 available, 60 held.
        bal = get_balance_breakdown(str(self.merchant.id))
        self.assertEqual(bal['available_paise'], 4_000)
        self.assertEqual(bal['held_paise'], 6_000)
        self.assertEqual(bal['total_paise'], 10_000)
