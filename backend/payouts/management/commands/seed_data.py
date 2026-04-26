"""
Seed the DB with realistic merchants, bank accounts, and credit history.

Usage:
    python manage.py seed_data
    python manage.py seed_data --reset    # wipes existing data first
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from payouts.models import (
    Merchant, BankAccount, LedgerEntry, Payout, IdempotencyKey,
)


SEEDS = [
    {
        'name': 'Acme Design Studio',
        'email': 'founder@acme-design.in',
        'bank': {
            'account_holder_name': 'Acme Design Studio Pvt Ltd',
            'account_number': '50100123456789',
            'ifsc_code': 'HDFC0001234',
        },
        # 5 customer payments, INR shown but stored as paise
        'credits': [
            (15000, 'Invoice #1024 - Stripe US'),
            (28000, 'Invoice #1025 - Wise UK'),
            (42000, 'Invoice #1026 - Stripe US'),
            (12000, 'Invoice #1027 - Razorpay'),
            (35000, 'Invoice #1028 - Wise EU'),
        ],
    },
    {
        'name': 'Brightline Freelance',
        'email': 'hi@brightline.dev',
        'bank': {
            'account_holder_name': 'Priya Sharma',
            'account_number': '00871700001234',
            'ifsc_code': 'ICIC0000871',
        },
        'credits': [
            (8500, 'Project advance - Acme client'),
            (17000, 'Milestone 1 - SaaS rebrand'),
            (22000, 'Milestone 2 - SaaS rebrand'),
        ],
    },
    {
        'name': 'Cloudpath Systems',
        'email': 'accounts@cloudpath.io',
        'bank': {
            'account_holder_name': 'Cloudpath Systems LLP',
            'account_number': '912020045678',
            'ifsc_code': 'AXIS0001212',
        },
        'credits': [
            (55000, 'Retainer - Q4 - Singapore client'),
            (55000, 'Retainer - Q1 - Singapore client'),
            (18000, 'Add-on integration work'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed merchants, bank accounts, and credit history.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Wipe payouts/ledger/idempotency first.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting data...')
            IdempotencyKey.objects.all().delete()
            LedgerEntry.objects.all().delete()
            Payout.objects.all().delete()
            BankAccount.objects.all().delete()
            Merchant.objects.all().delete()

        for seed in SEEDS:
            merchant, created = Merchant.objects.get_or_create(
                email=seed['email'],
                defaults={'name': seed['name']},
            )
            if created:
                self.stdout.write(f'  + Merchant: {merchant.name}')

                BankAccount.objects.create(merchant=merchant, **seed['bank'])

                # Credit history (in rupees in seed data, store as paise)
                for amount_rupees, description in seed['credits']:
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        amount_paise=amount_rupees * 100,
                        entry_type=LedgerEntry.EntryType.CREDIT,
                        description=description,
                    )
            else:
                self.stdout.write(f'  = Merchant exists: {merchant.name}')

        self.stdout.write(self.style.SUCCESS('\nSeed complete.'))
        for m in Merchant.objects.all():
            total = LedgerEntry.objects.filter(merchant=m).aggregate(
                t=Sum('amount_paise')
            )['t'] or 0
            self.stdout.write(
                f'  {m.name}: balance = ₹{total / 100:,.2f} '
                f'(merchant_id={m.id})'
            )
