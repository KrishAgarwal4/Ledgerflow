# Chronos System Architecture & Engineering Design

This document details the high-level architecture, transactional guarantees, and concurrency models implemented in **Chronos**.

---

## 1. System Overview & Component Topology

Chronos is comprised of five decoupled sub-engines interacting over a transactional PostgreSQL data layer:

```
[ Client / Developer Dashboard / Telemetry Collector ]
                         │
                         ▼
             [ FastAPI API Gateway ]
                         │
        ┌────────────────┼────────────────┬────────────────┐
        ▼                ▼                ▼                ▼
[ Ledger Engine ] [ Billing Engine ] [ Clock Engine ] [ Idempotency ]
        │                │                │                │
        └────────────────┴────────┬───────┴────────────────┘
                                  ▼
                      [ PostgreSQL 16 ACID DB ]
                     - Row Locks (FOR UPDATE)
                     - Append-Only Postings
                     - Zero-Sum Verification
```

### Component Responsibilities
1. **Ledger Engine (`backend/app/core/ledger_engine.py`):**
   - Implements immutable double-entry bookkeeping.
   - Computes account balances from postings on demand.
   - Enforces deadlock-free row locking by sorting account IDs before acquiring locks.
   - Enforces zero-sum balance checks ($\sum \text{Debit} == \sum \text{Credit}$).
2. **Billing Engine (`backend/app/core/billing_engine.py`):**
   - Evaluates metered usage against subscription plan tiers.
   - Computes down-to-the-second proration when tier changes occur mid-cycle.
   - Emits finalized invoices and links them to corresponding double-entry journal postings.
3. **Clock Engine (`backend/app/core/clock_engine.py`):**
   - Implements a **Discrete Event Simulation Loop**.
   - Maintains a virtual timeline independent of the host machine's wall clock (`datetime.now()`).
   - Sweeps milestone-by-milestone to trigger period rollovers, dunning retries, and invoice due dates.
4. **Dunning Engine (`backend/app/core/dunning_engine.py`):**
   - Implements Stripe's Smart Retries state machine.
   - Schedules retries at exponential backoff intervals (`+1 day`, `+3 days`, `+7 days`).
   - Automatically writes off uncollectible receivables to bad debt expenses upon terminal failure.
5. **Idempotency Manager (`backend/app/core/idempotency.py`):**
   - Hashes incoming payloads using SHA-256.
   - Uses PostgreSQL's primary key constraint on `idempotency_records` as an atomic compare-and-swap mutex.
   - Caches responses and returns `X-Idempotent-Replayed: true` on duplicate requests.

---

## 2. Invariants & Financial Correctness

| Invariant | Mechanism | Failure Mode |
| :--- | :--- | :--- |
| **No Float Inaccuracy** | Integer math with `BIGINT amount_cents`. | Python float division is prohibited. Integer division `//` and exact remainder distributions are used. |
| **Zero-Sum Postings** | $\sum_{\text{postings}} \text{Debit} == \sum_{\text{postings}} \text{Credit}$ | Aborts with `ZeroSumViolationError` (HTTP 400); transaction rolls back. |
| **Append-Only Immutability** | No `UPDATE` or `DELETE` statements on `ledger_postings`. | Corrections are recorded as reversing or offsetting journal entries. |
| **No Overdrafts on Wallets** | Pre-lock checks under `SELECT ... FOR UPDATE`. | Aborts with `InsufficientFundsError` (HTTP 422); wallet balance cannot be negative. |
| **Deadlock Elimination** | Accounts locked in strict alphabetical `id ASC` order. | Guarantees resource hierarchy; no cyclic dependency graph can form. |

---

## 3. Concurrency Model: Deterministic Lock Hierarchy

In standard multi-threaded financial services, transferring money between accounts $A$ and $B$ easily causes deadlocks:
- **Thread 1:** Transfers from $A \rightarrow B$ (Locks $A$, attempts to lock $B$).
- **Thread 2:** Transfers from $B \rightarrow A$ (Locks $B$, attempts to lock $A$).
- **Result:** Deadlock $\rightarrow$ transaction timeout or abort.

### Chronos Resolution
Chronos implements a strict **Total Resource Ordering**:
```python
unique_account_ids = sorted(list(set(p["account_id"] for p in postings)))
lock_stmt = (
    select(Account)
    .where(Account.id.in_(unique_account_ids))
    .order_by(Account.id.asc())
    .with_for_update()
)
```
Because all threads acquire locks in the exact same lexicographical order, a circular wait condition is mathematically impossible (Dijkstra's Resource Hierarchy Solution).

---

## 4. Discrete Event Simulation vs. Tick-Based Simulation

Traditional billing test clocks often increment time in fixed increments (e.g. 1 hour ticks in a while loop). For an advancement of 365 days, a tick-based approach would execute $365 \times 24 = 8,760$ database queries.

Chronos uses a **Discrete Event Simulation (DES)** solver:
1. Queries the database for the minimum upcoming milestone timestamp:
   $$t_{\text{next}} = \min(t_{\text{period\_end}}, t_{\text{next\_retry\_at}})$$
2. If $t_{\text{next}} \le t_{\text{target}}$, jumps virtual time directly to $t_{\text{next}}$, executes all events due at that instant, flushes updates, and repeats.
3. If no pending events exist before $t_{\text{target}}$, virtual time leaps directly to $t_{\text{target}}$.
- **Complexity:** $O(M)$ where $M$ is the number of actual state transitions (typically 1 to 5), executing in $<50\text{ms}$ rather than thousands of empty ticks.
