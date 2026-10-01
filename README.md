# Ledgerflow (Chronos) — Immutable Double-Entry Ledger & Virtual Test Clock Billing Engine

[![Chronos CI](https://github.com/KrishAgarwal4/Ledgerflow/actions/workflows/ci.yml/badge.svg)](https://github.com/KrishAgarwal4/Ledgerflow/actions)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat&logo=postgresql)](https://www.postgresql.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00?style=flat&logo=sqlalchemy)](https://www.sqlalchemy.org)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-orange?style=flat)](https://alembic.sqlalchemy.org)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v4-38B2AC?style=flat&logo=tailwind-css)](https://tailwindcss.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Ledgerflow (Chronos)** is an immutable double-entry accounting ledger, usage metering pipeline, and deterministic virtual time simulator ("Test Clocks") built for high-throughput billing under concurrency.

Designed around Stripe's core financial and systems engineering principles: **zero-sum balance invariants**, **deadlock-free concurrency via deterministic lock ordering**, **SHA-256 idempotency deduplication under replay storms**, and **down-to-the-second proration with automated smart dunning retries**.

---

## 🏛️ System Architecture

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

Detailed architectural diagrams and sequence flows can be found in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).

---

## 📚 Architecture Decision Records (ADRs)

Chronos is built with rigorous systems engineering documentation. Each core design decision is documented with trade-off analysis:

- **[ADR 0001: Immutable Double-Entry Accounting & Zero-Sum Invariants](docs/adr/0001-double-entry-accounting-and-zero-sum-invariants.md)**
  - *Context:* Why mutable `UPDATE balance` queries cause audit loss, phantom overwrites, and IEEE 754 float drift.
  - *Solution:* Append-only journal postings, positive integer cents (`BIGINT`), and runtime zero-sum verification.
- **[ADR 0002: Deterministic Lock Hierarchy for Deadlock Prevention](docs/adr/0002-deterministic-locking-order-deadlock-prevention.md)**
  - *Context:* Preventing cyclic dependency deadlocks during parallel multi-account transfers.
  - *Solution:* Mathematical proof of deadlock freedom by acquiring row locks in strict lexicographical order (`ORDER BY id ASC FOR UPDATE`).
- **[ADR 0003: Distributed Idempotency Protocol & SHA-256 Fingerprinting](docs/adr/0003-distributed-idempotency-and-payload-hashing.md)**
  - *Context:* Handling network replay storms and concurrent webhook retries without double-charging.
  - *Solution:* PostgreSQL primary key constraint as an atomic compare-and-swap mutex, parameter fingerprinting, and cached response replays.
- **[ADR 0004: Virtual Test Clock Architecture & Discrete Event Simulation](docs/adr/0004-virtual-test-clock-discrete-event-simulation.md)**
  - *Context:* Eliminating `datetime.now()` and tick-based simulation overhead.
  - *Solution:* Discrete Event Simulation (DES) queue, down-to-the-second proration math, and 3-step exponential dunning retry lifecycle.

---

## ⚡ Concurrency & Chaos Stress Testing

Chronos includes built-in stress test harnesses accessible via the Developer UI, CLI, or API:

### 1. 100 Duplicate Event Storm (`POST /v1/chaos/meter-storm`)
Fires 100 concurrent async tasks with the identical `event_id` in $<100\text{ms}$.
- **Result:** Exactly 1 creates the record (`HTTP 201`), 99 return cached receipts (`HTTP 200` with `X-Idempotent-Replayed: true`).

### 2. Parallel Overdraft Race Condition (`POST /v1/chaos/overdraft-race`)
Fires 20 simultaneous $\$10.00$ ($1,000$ cents) spend requests against a customer wallet with a $\$50.00$ ($5,000$ cents) prepaid balance.
- **Result:** Under `SELECT ... FOR UPDATE`, exactly 5 charges succeed ($\$50.00$), and 15 are cleanly rejected with `InsufficientFundsError`.
- **Invariant:** Final wallet balance is strictly **$\$0.00$**, never negative!

---

## 🖥️ Developer CLI Tool

You can inspect the ledger, verify mathematical balance, advance virtual time, or run stress tests directly from your terminal:

```bash
# Check system status & zero-sum balance proof
python -m backend.cli status

# Inspect all live T-Account balances
python -m backend.cli ledger balance

# Advance the virtual simulation clock by 30 days
python -m backend.cli clock advance --days 30

# Launch a 100-request duplicate meter storm
python -m backend.cli stress duplicate-storm --count 100

# Launch a 20-thread parallel overdraft race condition
python -m backend.cli stress overdraft-race --count 20
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker Compose)

### 1. Run with Docker Compose
```bash
docker compose up --build
```
- **Developer Console:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run Locally (Native Development)
```bash
# Setup virtual environment and dependencies
make setup

# Run database migrations
make migrate

# Seed baseline AI SaaS tiers & customers
make seed

# Start backend (Port 8000)
make dev-backend

# Start frontend (Port 5173)
make dev-frontend
```

---

## 🧪 Automated Test Suite (100% Passing)

Run the full async concurrency, invariant, and state machine test suite:

```bash
make test
```

```
backend/tests/test_clocks.py::test_proration_calculation PASSED          [ 11%]
backend/tests/test_clocks.py::test_test_clock_cycle_rollover_and_ledger_posting PASSED [ 22%]
backend/tests/test_concurrency.py::test_parallel_overdraft_race_condition PASSED [ 33%]
backend/tests/test_dunning.py::test_dunning_retry_lifecycle PASSED       [ 44%]
backend/tests/test_idempotency.py::test_meter_event_idempotency_concurrent PASSED [ 55%]
backend/tests/test_idempotency.py::test_idempotency_payload_mismatch PASSED [ 66%]
backend/tests/test_ledger.py::test_zero_sum_enforcement PASSED           [ 77%]
backend/tests/test_ledger.py::test_positive_cents_enforcement PASSED     [ 88%]
backend/tests/test_ledger.py::test_balanced_transaction_and_global_proof PASSED [100%]

============================== 9 passed in 1.58s ===============================
```

### Run Concurrency Benchmarks
```bash
make benchmark
```
Measures throughput and latency percentiles ($p_{50}, p_{95}, p_{99}$) under 20 concurrent worker tasks:
```
============================================================
 CHRONOS CONCURRENCY BENCHMARK (20 WORKERS, 100 REQUESTS)
============================================================
 Total Transactions Processed: 100
 Total Wall Time:             0.246 s
 Throughput:                   406.9 req/s
 Latency p50 (Median):         22.69 ms
 Latency p95:                  137.47 ms
 Latency p99:                  159.48 ms
============================================================
```

---

## 📡 API Reference

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

## 📄 License
MIT License. Built by [Krish Agarwal](https://github.com/KrishAgarwal4).
