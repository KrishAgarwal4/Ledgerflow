# Ledgerflow

A double-entry accounting ledger, usage-based billing engine, and virtual test clock simulator built with FastAPI, PostgreSQL, SQLAlchemy 2.0 (AsyncPG), and React.

I built this project to understand how production billing infrastructure handles concurrency, balance correctness, and deterministic time simulation. It specifically addresses four core problems:

1. **Balance Correctness:** Eliminating mutable `UPDATE accounts SET balance = balance + x` queries in favor of an append-only, zero-sum double-entry ledger.
2. **Deadlock Prevention:** Enforcing a deterministic resource lock hierarchy by sorting account IDs prior to acquiring row locks (`SELECT ... FOR UPDATE`).
3. **Idempotent Ingestion:** Deduplicating incoming meter events during network retry storms using SHA-256 parameter hashing and atomic database constraints.
4. **Deterministic Time Travel:** Replacing wall-clock checks (`datetime.now()`) with a Discrete Event Simulation (DES) test clock that advances through subscription renewals, exact proration math, and dunning retries.

---

## Architecture Overview

```
                      +---------------------------------------+
                      |       Virtual Test Clock Engine       |
                      |   (Discrete Event Simulation Queue)   |
                      +-------------------+-------------------+
                                          |
                                          v (Virtual Time)
                      +---------------------------------------+
                      |      Billing & Metering Pipeline      |
                      |  - Down-to-the-second Proration       |
                      |  - Usage Aggregation & Invoicing      |
                      |  - Dunning State Machine (+1d, +3d, +7d)
                      +-------------------+-------------------+
                                          |
                                          v (Emits Journal Entries)
                      +---------------------------------------+
                      |     Immutable Double-Entry Ledger     |
                      |  - Append-only (No UPDATEs or DELETEs)|
                      |  - Zero-sum: SUM(Debit) == SUM(Credit)|
                      |  - Deterministic Lock Hierarchy       |
                      +---------------------------------------+
```

Detailed component breakdowns and sequence flows are documented in [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md).

---

## Core Invariants

### 1. Append-Only Double-Entry Math
Traditional billing systems that store balance as a mutable column suffer from lost updates and lack an audit trail. Ledgerflow treats balances as a derived view over immutable postings:

- **Asset and Expense Accounts:**
  $$\text{Balance} = \sum \text{Debits} - \sum \text{Credits}$$
- **Liability, Equity, and Revenue Accounts:**
  $$\text{Balance} = \sum \text{Credits} - \sum \text{Debits}$$

Every entry must strictly balance to zero:
$$\sum \text{Debit} - \sum \text{Credit} = 0$$

If any transaction violates this equality down to a single cent, it is rolled back immediately with a `ZeroSumViolationError`. All currency values use integer cents (`BIGINT amount_cents`) to eliminate floating-point rounding errors.

### 2. Deadlock-Free Concurrency
When concurrent transactions transfer funds between overlapping accounts, acquiring locks in arbitrary order can produce circular wait deadlocks:
- Transaction 1 locks Account A, then waits for Account B.
- Transaction 2 locks Account B, then waits for Account A.

Ledgerflow avoids this by sorting all account IDs lexicographically before acquiring row-level locks:
```python
unique_account_ids = sorted(list(set(p["account_id"] for p in postings)))
lock_stmt = (
    select(Account)
    .where(Account.id.in_(unique_account_ids))
    .order_by(Account.id.asc())
    .with_for_update()
)
```
Because every transaction acquires locks in the same global order, circular wait conditions cannot form.

### 3. Idempotent Ingestion Pipeline
When clients or webhooks retry requests due to network timeouts, the server must avoid double-recording usage or charges:
1. The request path and normalized JSON payload are hashed with SHA-256.
2. The incoming `Idempotency-Key` (or `event_id`) is claimed in the `idempotency_records` table with status `PROCESSING`.
3. If concurrent requests arrive with the same key, PostgreSQL's primary key constraint serializes them: one worker proceeds while others detect the in-flight state and return HTTP 409 (or wait to retrieve the cached result).
4. Completed requests cache the HTTP status code and response payload. Subsequent calls return the cached response with an `X-Idempotent-Replayed: true` header.
5. If an existing key is reused with different payload parameters, the server detects the hash mismatch and rejects the request with HTTP 422.

### 4. Virtual Test Clock & Proration Math
Testing recurring billing, mid-cycle plan changes, and payment retries is difficult when logic relies on system time. In Ledgerflow, all billing logic accepts an explicit virtual timestamp.

Advancing the clock uses a Discrete Event Simulation (DES) loop:
1. It queries the next earliest milestone (billing cycle rollover or scheduled retry).
2. It advances virtual time directly to that timestamp, executes the state transition, records an audit log entry in `clock_milestones`, and repeats until the target time is reached.
3. Mid-cycle upgrades/downgrades compute exact proration to the second:
   $$\text{Credit} = \left\lfloor \text{old\_fee} \times \frac{t_{\text{end}} - t_{\text{change}}}{t_{\text{end}} - t_{\text{start}}} \right\rfloor, \quad \text{Charge} = \left\lfloor \text{new\_fee} \times \frac{t_{\text{end}} - t_{\text{change}}}{t_{\text{end}} - t_{\text{start}}} \right\rfloor$$
4. Payment failures trigger an exponential dunning schedule (+1 day, +3 days, +7 days). If all retries fail, the subscription transitions to `CANCELED`, the invoice is marked `UNCOLLECTIBLE`, and a bad-debt write-off is recorded in the ledger.

---

## Design Documents

Engineering design choices and trade-offs are documented in the Architecture Decision Records (ADRs):

- [ADR 0001: Immutable Double-Entry Accounting & Zero-Sum Invariants](docs/adr/0001-double-entry-accounting-and-zero-sum-invariants.md)
- [ADR 0002: Deterministic Lock Hierarchy for Deadlock Prevention](docs/adr/0002-deterministic-locking-order-deadlock-prevention.md)
- [ADR 0003: Distributed Idempotency Protocol & SHA-256 Fingerprinting](docs/adr/0003-distributed-idempotency-and-payload-hashing.md)
- [ADR 0004: Virtual Test Clock Architecture & Discrete Event Simulation](docs/adr/0004-virtual-test-clock-discrete-event-simulation.md)

---

## Concurrency & Stress Tests

The application includes built-in endpoints and test scripts to simulate common failure modes:

### 1. 100 Duplicate Event Storm (`POST /v1/chaos/meter-storm`)
Fires 100 concurrent async requests with the identical `event_id` in under 100ms.
- **Expected Result:** Exactly 1 record is written to the database (HTTP 201); 99 are returned as cached replays (HTTP 200 with `X-Idempotent-Replayed: true`).

### 2. Parallel Overdraft Race Condition (`POST /v1/chaos/overdraft-race`)
Fires 20 simultaneous $10 charges against a $50 prepaid wallet balance.
- **Expected Result:** Exactly 5 charges succeed ($50 total), and 15 are rejected with `InsufficientFundsError`.
- **Invariant:** Final wallet balance is verified to be strictly $0.00, never negative.

---

## CLI Tool

The project includes a command-line interface to inspect the ledger and test simulations directly from the terminal:

```bash
# View system status & zero-sum balance proof
python -m backend.cli status

# Inspect live T-Account balances formatted as an ASCII table
python -m backend.cli ledger balance

# Advance the virtual simulation clock by 30 days
python -m backend.cli clock advance --days 30

# Launch a 100-request duplicate meter storm
python -m backend.cli stress duplicate-storm --count 100

# Launch a 20-thread parallel overdraft race condition
python -m backend.cli stress overdraft-race --count 20
```

---

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker)

### Option 1: Docker Compose
```bash
docker compose up --build
```
- Dashboard: http://localhost:3000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development
```bash
# Setup virtual environment and dependencies
make setup

# Run Alembic migrations
make migrate

# Seed initial accounts and plans
make seed

# Start backend (Port 8000)
make dev-backend

# Start frontend (Port 5173)
make dev-frontend
```

---

## Testing

Run the full pytest suite (concurrency, invariants, dunning, and idempotency):

```bash
make test
```

Sample output:
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

### Concurrency Benchmark
To measure transaction throughput and latency percentiles under concurrent load:
```bash
make benchmark
```

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

## API Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/v1/ledger/accounts` | Live computed balances from postings |
| `GET` | `/v1/ledger/journal-entries` | Append-only transaction log with balanced postings |
| `GET` | `/v1/ledger/verify` | Zero-sum proof ($\sum \text{Debit} == \sum \text{Credit}$) |
| `POST` | `/v1/meter-events` | Ingest usage event with idempotency deduplication |
| `GET` | `/v1/test-clocks` | Virtual clock state and milestone history |
| `POST` | `/v1/test-clocks/{id}/advance` | Advance virtual time across scheduled milestones |
| `POST` | `/v1/test-clocks/reset` | Reset simulation database to canonical clean state |
| `GET` | `/v1/customers` | Customers, prepaid balances, and active subscriptions |
| `POST` | `/v1/subscriptions/{id}/preview-proration` | Live down-to-the-second proration preview |
| `POST` | `/v1/subscriptions/{id}/change-plan` | Execute mid-cycle tier change with journal entry |
| `POST` | `/v1/chaos/meter-storm` | Fire 100 concurrent duplicate meter events |
| `POST` | `/v1/chaos/overdraft-race` | Fire 20 concurrent spends against prepaid wallet |

---

## License
MIT License. Built by [Krish Agarwal](https://github.com/KrishAgarwal4).
