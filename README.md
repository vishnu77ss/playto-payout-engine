# Playto Payout Engine

A minimal but production-shaped payout engine for the Playto Founding
Engineer challenge. Merchants accumulate balance from simulated customer
payments and can request payouts to their Indian bank account. The
engine handles the hard parts: concurrency, idempotency, an explicit
state machine, and a retry sweep for stuck transfers.

> See **EXPLAINER.md** for the design walkthrough, architecture / ER /
> workflow diagrams, and the answers to the five challenge questions.

---

## Stack

| Layer       | Tech                                          |
| ----------- | --------------------------------------------- |
| Backend     | Django 5.1 + Django REST Framework            |
| Database    | PostgreSQL 16                                 |
| Worker      | Celery 5 + Redis                              |
| Frontend    | React 18 + Vite + Tailwind                    |
| Infra (dev) | Docker Compose for Postgres + Redis           |

---

## Folder structure

```
playto-payout-engine/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── playto/                       # Django project (settings, urls, celery)
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── wsgi.py / asgi.py
│   └── payouts/                      # The single Django app
│       ├── models.py                 # Merchant, BankAccount, Payout, LedgerEntry, IdempotencyKey
│       ├── services.py               # create_payout, balance breakdown
│       ├── state_machine.py          # Allowed transitions + atomic transition_payout
│       ├── tasks.py                  # Celery tasks: process_payout, retry_stuck_payouts
│       ├── views.py                  # DRF endpoints
│       ├── serializers.py
│       ├── urls.py
│       ├── exceptions.py
│       ├── admin.py
│       ├── management/commands/
│       │   └── seed_data.py          # Seeds 3 merchants with credit history
│       └── tests/
│           ├── test_concurrency.py
│           └── test_idempotency.py
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx, App.jsx, api.js, index.css
│       └── components/
│           ├── Dashboard.jsx
│           ├── BalanceCard.jsx
│           ├── PayoutForm.jsx
│           ├── PayoutTable.jsx
│           └── TransactionList.jsx
├── diagrams/                         # ER, workflow, architecture (Excalidraw + Mermaid)
├── docker-compose.yml                # Postgres + Redis only
├── EXPLAINER.md                      # Design + diagrams + 5 answers
└── README.md
```

---

## Prerequisites

- Python **3.10+** (tested on 3.13)
- Node.js 18+
- Docker Desktop (recommended — gives you Postgres + Redis with one
  command). If you don't want Docker, see "Without Docker" further down.

---

## Setup — step by step

### 1. Start Postgres + Redis (Docker, recommended)

From the repository root:

```bash
docker compose up -d
```

This starts Postgres on `localhost:5432` and Redis on `localhost:6379`.
Stop them later with `docker compose down`.

### 2. Backend

```bash
cd backend

# Create and activate a virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env       # Windows
# or:  cp .env.example .env  # macOS/Linux

# Run migrations and seed
python manage.py migrate
python manage.py seed_data

# Optional: a Django admin user so you can browse /admin/
python manage.py createsuperuser

# Run the API
python manage.py runserver 0.0.0.0:8000
```

The API is now at `http://localhost:8000/api/v1/`.

### 3. Celery worker + beat (in two new terminals)

In one terminal — the worker that processes payouts:

```bash
cd backend
.venv\Scripts\activate          # or: source .venv/bin/activate
# Windows note: use --pool=solo because Celery's default prefork pool
# does not support Windows.
celery -A playto worker -l info --pool=solo
# macOS/Linux can drop --pool=solo:
# celery -A playto worker -l info
```

In another terminal — beat, which fires the periodic sweep every 10s:

```bash
cd backend
.venv\Scripts\activate
celery -A playto beat -l info
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

---

## Without Docker (native Postgres + Redis)

### Postgres

1. Install Postgres 14+ from https://www.postgresql.org/download/.
2. Open `psql` (or pgAdmin) and run:
   ```sql
   CREATE USER playto WITH PASSWORD 'playto';
   CREATE DATABASE playto OWNER playto;
   GRANT ALL PRIVILEGES ON DATABASE playto TO playto;
   ```
3. Make sure `backend/.env` matches your host/port (defaults are
   `localhost:5432`).

### Redis

- Linux/macOS: `brew install redis && brew services start redis` (or
  your distro's package manager).
- Windows: easiest is Memurai (https://www.memurai.com/) or run Redis
  through the Docker container above.

---

## How to test

### Automated tests

```bash
cd backend
.venv\Scripts\activate
python manage.py test payouts.tests
```

This runs the two required tests:

- `test_concurrency.py` — two threads each request ₹60 from a ₹100
  balance; only one gets a 201.
- `test_idempotency.py` — same key returns the same payout id and never
  creates a duplicate; reusing the key with a different body returns
  409 Conflict.

### API smoke test (curl)

After `seed_data`, list merchants and grab an ID:

```bash
curl http://localhost:8000/api/v1/merchants/
```

Then check balance:

```bash
curl http://localhost:8000/api/v1/merchants/<MERCHANT_ID>/balance/
```

Request a payout (note the **Idempotency-Key** header):

```bash
curl -X POST http://localhost:8000/api/v1/merchants/<MERCHANT_ID>/payouts/request/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"amount_paise": 5000, "bank_account_id": "<BANK_ID>"}'
```

Run the same curl twice with the **same** `Idempotency-Key` — you get the
same response back, only one payout in the DB.

### UI test

Open http://localhost:5173, pick a merchant, submit a payout. The table
auto-refreshes every 2s and you should see status flip
`pending → processing → completed`/`failed`.

---

## API reference

| Method | Path                                                | Notes                          |
| ------ | --------------------------------------------------- | ------------------------------ |
| GET    | `/api/v1/merchants/`                                | List merchants                 |
| GET    | `/api/v1/merchants/{id}/balance/`                   | available / held / total       |
| GET    | `/api/v1/merchants/{id}/ledger/`                    | Last 50 ledger entries         |
| GET    | `/api/v1/merchants/{id}/bank-accounts/`             |                                |
| GET    | `/api/v1/merchants/{id}/payouts/`                   | Last 50 payouts                |
| POST   | `/api/v1/merchants/{id}/payouts/request/`           | Requires `Idempotency-Key`     |

Request body for the POST:

```json
{ "amount_paise": 5000, "bank_account_id": "uuid-of-merchant-bank-account" }
```

---

## Notes

- All amounts are stored as `BigIntegerField` in **paise**. There are
  no `FloatField` or `DecimalField` columns anywhere — see
  EXPLAINER.md for why.
- Migrations are committed empty (`migrations/__init__.py`). Run
  `python manage.py makemigrations payouts` once on first setup if
  Django prompts you.
