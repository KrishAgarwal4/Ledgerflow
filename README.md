# Chronos — Immutable Double-Entry Ledger & Virtual Test Clock Billing Engine

[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat&logo=postgresql)](https://www.postgresql.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=flat&logo=sqlalchemy)](https://www.sqlalchemy.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4-38B2AC?style=flat&logo=tailwind-css)](https://tailwindcss.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Chronos** is a high-craft financial billing engine and deterministic time simulator built to Stripe engineering standards. It solves the hardest distributed systems problems in FinTech: **zero-sum balance invariants**, **deadlock-free concurrency**, **idempotent metering under network replay storms**, and **down-to-the-second subscription proration with automated smart retries (dunning)**.

---

## 🏛️ Architectural Pillars

```
                     ┌──────────────────────────────────────────────┐
                     │          Chronos Virtual Test Clock          │
                     │  (Discrete Event Simulation Engine)          │
                     └──────────────────────┬───────────────────────┘
                                            │ Advances Virtual Time
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │         Billing & Subscription Engine        │
                     │  - Exact-Second Proration Math               │
                     │  - Usage Metering Aggregation                │
                     │  - Smart Dunning Machine (+1d, +3d, +7d)     │
                     └──────────────────────┬───────────────────────┘
                                            │ Emits Journal Entries
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │       Immutable Double-Entry Ledger          │
                     │  - Zero `UPDATE balance` queries             │
                     │  - Strict Zero-Sum: SUM(Debit) == SUM(Credit)│
                     │  - Deterministic Lock Order: Deadlock-Free   │
                     └──────────────────────────────────────────────┘
```

### Pillar A: Immutable Double-Entry Accounting Ledger
Traditional CRUD applications maintain account balances with mutable updates (`UPDATE accounts SET balance = balance + :amount`). In financial systems, this creates race conditions, audit loss, and drift.

Chronos enforces strict **Immutable Double-Entry Bookkeeping**:
1. **Append-Only Invariant:** No `UPDATE` or `DELETE` is ever executed on `journal_entries` or `ledger_postings`. Account balances are strictly derived from the sum of postings:
   $$\text{Asset, Expense Balance} = \sum \text{Debits} - \sum \text{Credits}$$
   $$\text{Liability, Revenue Balance} = \sum \text{Credits} - \sum \text{Debits}$$
2. **Zero-Sum Mathematical Invariant:** Every journal entry must satisfy:
   $$\sum \text{DEBIT} - \sum \text{CREDIT} = 0$$
   Any transaction violating this invariant triggers an immediate `ZeroSumViolationError` and rolls back the database transaction.
3. **Deadlock-Free Row-Level Locking:** When debiting and crediting accounts under high concurrency, parallel transactions locking accounts in differing order will deadlock. Chronos extracts all unique account IDs involved in a journal entry, sorts them alphabetically (`ORDER BY id ASC`), and acquires row locks via `SELECT ... FOR UPDATE`. This guarantees a strict global lock hierarchy and eliminates deadlocks.

### Pillar B: Idempotent Event Ingestion Pipeline
Distributed webhook senders and telemetry meter collectors retry on network failure. Without strict idempotency, retries lead to double-billing.

1. `POST /v1/meter-events` accepts an `event_id` (or `Idempotency-Key` header).
2. The payload and path are hashed using **SHA-256**.
3. **Atomic Mutual Exclusion:** PostgreSQL's primary key constraint on `idempotency_records` acts as an atomic compare-and-swap mutex:
   - Worker 1 inserts the key in `PROCESSING` status.
   - Concurrent workers catch `UniqueViolationError`, recognize the in-flight state, and return HTTP `409 Conflict`.
4. Upon successful event ingestion, the record transitions to `SUCCEEDED` with the cached response payload.
5. All subsequent duplicate requests receive the cached receipt with the response header:
   `X-Idempotent-Replayed: true`
6. If the client reuses an existing key with tampered parameters, Chronos detects the SHA-256 mismatch and rejects with HTTP `422 Unprocessable Entity`.

### Pillar C: Deterministic "Test Clocks" (Time Travel Engine)
Business logic NEVER calls `datetime.now()`. All billing evaluations read the current virtual time from the `test_clocks` table.

When `POST /v1/test-clocks/{id}/advance` is called:
1. Chronos initiates a **Discrete Event Simulation**:
   - Queries the earliest upcoming milestones between $t_{\text{current}}$ and $t_{\text{target}}$:
     - Billing cycle rollovers (`current_period_end`)
     - Dunning retries (`next_retry_at`)
2. Advances time chronologically milestone-by-milestone:
   - **Cycle Rollover:** Aggregates unbilled usage, computes tiered overage fees, generates finalized `Invoice`, and records double-entry postings:
     - `DEBIT Customer_Accounts_Receivable`
     - `CREDIT Platform_Revenue`
   - **Payment Execution:** If payment succeeds, settles invoice from prepaid wallet or card cash.
   - **Dunning State Machine:** If payment fails (e.g. `payment_method_status == FAIL_ALWAYS`):
     - Milestone 1: Transitions `ACTIVE` $\rightarrow$ `PAST_DUE`, schedules Retry 1 in `+1 day`.
     - Milestone 2: Retry 1 fails $\rightarrow$ schedules Retry 2 in `+3 days`.
     - Milestone 3: Retry 2 fails $\rightarrow$ schedules Retry 3 in `+7 days`.
     - Milestone 4: Retry 3 fails $\rightarrow$ transitions `PAST_DUE` $\rightarrow$ `CANCELED`, marks invoice `UNCOLLECTIBLE`, and posts bad debt write-off:
       - `DEBIT Bad_Debt_Expense`
       - `CREDIT Customer_Accounts_Receivable`
3. **Exact Down-To-The-Second Proration Math:** Mid-cycle tier upgrades compute unused credit on the old plan and prorated charge on the new plan:
   $$\text{Credit} = \left\lfloor \text{old\_fee} \times \frac{t_{\text{end}} - t_{\text{change}}}{t_{\text{end}} - t_{\text{start}}} \right\rfloor, \quad \text{Charge} = \left\lfloor \text{new\_fee} \times \frac{t_{\text{end}} - t_{\text{change}}}{t_{\text{end}} - t_{\text{start}}} \right\rfloor$$

---

## ⚡ Chaos & Concurrency Stress Testing

Chronos includes built-in stress test harnesses accessible via the UI or API:

### 1. 100 Duplicate Event Storm (`POST /v1/chaos/meter-storm`)
Fires 100 concurrent async tasks with the identical `event_id` in $<100\text{ms}$.
- **Result:** Exactly 1 creates the record (`HTTP 201`), 99 return cached receipts (`HTTP 200` with `X-Idempotent-Replayed: true`).

### 2. Parallel Overdraft Race Condition (`POST /v1/chaos/overdraft-race`)
Fires 20 simultaneous $\$10.00$ ($1,000$ cents) spend requests against a customer wallet with a $\$50.00$ ($5,000$ cents) prepaid balance.
- **Result:** Under `SELECT ... FOR UPDATE`, exactly 5 charges succeed ($\$50.00$), and 15 are cleanly rejected with `InsufficientFundsError`.
- **Invariant:** Final wallet balance is strictly **$\$0.00$**, never negative!

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker Compose)

### 1. Clone & Setup
```bash
git clone https://github.com/your-username/chronos-billing.git
cd chronos-billing

# Install backend dependencies
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt

# Install frontend dependencies
npm --prefix frontend install
```

### 2. Run with Docker Compose (Recommended)
```bash
docker compose up --build
```
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Run Locally (Native)
```bash
# Seed database with baseline AI SaaS tiers & customers
make seed

# Start backend (Port 8000)
make dev-backend

# Start frontend (Port 5173)
make dev-frontend
```

---

## 🧪 Automated Test Suite

Chronos comes with a comprehensive suite of async concurrency, invariant, and state machine tests:

```bash
make test
```

### Test Coverage Highlights:
- `test_ledger.py`: Zero-sum enforcement, positive integer cents check, balance calculation across all 5 account types.
- `test_concurrency.py`: 20-thread parallel spend race condition with row-level locks.
- `test_idempotency.py`: 50 concurrent requests with identical keys, tampered payload mismatch rejection (HTTP 422).
- `test_clocks.py`: Deterministic +30 days virtual time advancement, usage aggregation, invoice generation.
- `test_dunning.py`: Complete 3-step dunning failure lifecycle (`ACTIVE` $\rightarrow$ `PAST_DUE` $\rightarrow$ `CANCELED` with ledger write-off).

---

## 📡 API Reference Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/ledger/accounts` | Live computed account balances directly from postings |
| `GET` | `/v1/ledger/journal-entries` | Append-only transaction log with balanced postings |
| `GET` | `/v1/ledger/verify` | Global mathematical zero-sum proof ($\sum \text{Debit} == \sum \text{Credit}$) |
| `POST` | `/v1/meter-events` | Ingest usage event with atomic idempotency deduplication |
| `GET` | `/v1/test-clocks` | Current virtual clock time and milestone history |
| `POST` | `/v1/test-clocks/{id}/advance` | Deterministically advance virtual time across milestones |
| `POST` | `/v1/test-clocks/reset` | Reset simulation database to canonical clean state |
| `GET` | `/v1/customers` | Customers, prepaid wallet balances, and active subscriptions |
| `POST` | `/v1/subscriptions/{id}/preview-proration` | Live down-to-the-second proration preview |
| `POST` | `/v1/subscriptions/{id}/change-plan` | Execute mid-cycle tier change with double-entry adjustment |
| `POST` | `/v1/chaos/meter-storm` | Fire 100 concurrent duplicate meter events |
| `POST` | `/v1/chaos/overdraft-race` | Fire 20 concurrent spends against prepaid wallet balance |

---

## 🛠️ Tech Stack & Design Choices

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (AsyncPG), Pydantic v2.
- **Database:** PostgreSQL 16 with ACID transactions and row-level locking (`SELECT ... FOR UPDATE`).
- **Currency Arithmetic:** Strict integer cents (`BIGINT amount_cents`). Floating-point numbers are strictly forbidden.
- **Frontend:** React 19, Vite, TypeScript, Tailwind CSS v4, Lucide Icons.
- **Design System:** Obsidian dark mode, Stripe-inspired typography and telemetry badges.

---

## 📄 License
MIT License. Built for Stripe Systems & Engineering Portfolio.
