"""
Idempotency test:

  1. First POST with key K -> creates payout, returns 201.
  2. Second POST with key K (same body) -> returns the SAME response,
     no second payout created.
  3. Third POST with key K but DIFFERENT body -> 409 conflict.
"""
import uuid

from django.test import TestCase

from payouts.exceptions import IdempotencyConflict
from payouts.models import (
    BankAccount, LedgerEntry, Merchant, Payout,
)
from payouts.services import create_payout


class IdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Idem Co', email='i@x.com'
        )
        self.bank = BankAccount.objects.create(
            merchant=self.merchant,
            account_number='999888777666',
            ifsc_code='HDFC0009999',
            account_holder_name='Idem Co',
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=20_000,
            entry_type=LedgerEntry.EntryType.CREDIT,
            description='seed credit',
        )

    def test_repeated_key_returns_same_response(self):
        key = str(uuid.uuid4())
        body = {
            'amount_paise': 5_000,
            'bank_account_id': str(self.bank.id),
        }

        r1 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=5_000,
            bank_account_id=str(self.bank.id),
            idempotency_key=key,
            request_body=body,
        )
        r2 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=5_000,
            bank_account_id=str(self.bank.id),
            idempotency_key=key,
            request_body=body,
        )

        # Same payout id in both responses
        self.assertEqual(r1['body']['id'], r2['body']['id'])
        self.assertEqual(r1['status_code'], 201)
        self.assertEqual(r2['status_code'], 201)
        self.assertFalse(r1['replayed'])
        self.assertTrue(r2['replayed'])

        # Exactly one payout in DB.
        self.assertEqual(
            Payout.objects.filter(merchant=self.merchant).count(), 1,
        )

    def test_same_key_different_body_raises_conflict(self):
        key = str(uuid.uuid4())

        create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=5_000,
            bank_account_id=str(self.bank.id),
            idempotency_key=key,
            request_body={
                'amount_paise': 5_000,
                'bank_account_id': str(self.bank.id),
            },
        )

        with self.assertRaises(IdempotencyConflict):
            create_payout(
                merchant_id=str(self.merchant.id),
                amount_paise=9_999,  # different amount with same key
                bank_account_id=str(self.bank.id),
                idempotency_key=key,
                request_body={
                    'amount_paise': 9_999,
                    'bank_account_id': str(self.bank.id),
                },
            )

        # Still only one payout.
        self.assertEqual(
            Payout.objects.filter(merchant=self.merchant).count(), 1,
        )
