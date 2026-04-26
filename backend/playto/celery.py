import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'playto.settings')

app = Celery('playto')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic sweep: every 10 seconds, look for payouts stuck in PROCESSING for >30s
# and retry / fail them with exponential backoff.
app.conf.beat_schedule = {
    'retry-stuck-payouts-every-10s': {
        'task': 'payouts.tasks.retry_stuck_payouts',
        'schedule': 10.0,
    },
    'cleanup-expired-idempotency-keys-hourly': {
        'task': 'payouts.tasks.cleanup_expired_idempotency_keys',
        'schedule': 3600.0,
    },
}
