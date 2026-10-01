# ADR 0001: Immutable Double-Entry Accounting & Zero-Sum Invariants

## Status
Accepted

## Context
In billing and FinTech applications, account balances are frequently represented as a mutable column:
```sql
UPDATE accounts SET balance = balance + 500 WHERE id = 'acc_123';
```
While simple, mutable balances suffer from catastrophic failure modes in high-throughput environments:
1. **Lost Updates & Phantom Overwrites:** Race conditions between simultaneous read-modify-write transactions can overwrite parallel deposits or spends.
2. **Audit Loss:** Overwriting a balance destroys the historical audit trail. If a customer's balance is wrong, it is impossible to determine which transaction corrupted it.
3. **Floating Point Drift:** Using floating point data types (`FLOAT`, `DOUBLE PRECISION`) introduces IEEE 754 precision errors (e.g. `0.1 + 0.2 = 0.30000000000000004`).

## Decision
We enforce strict **Immutable Double-Entry Accounting** modeled after Stripe Ledger:
1. **Append-Only Postings:** Balances are never modified directly. Every movement of funds is recorded as an immutable `JournalEntry` with at least two `LedgerPosting` rows.
2. **Strict Zero-Sum Enforcement:** Every transaction must verify that:
   $$\sum \text{Debit} == \sum \text{Credit}$$
   If an unbalanced entry is submitted, the transaction aborts with `ZeroSumViolationError`.
3. **Integer Cents Representation:** All monetary values are represented as positive `BIGINT` integer cents.
4. **Calculated Balances:** Account balances are computed directly from the postings according to accounting classification:
   - **Asset & Expense Accounts:** Balance = $\sum \text{Debits} - \sum \text{Credits}$
   - **Liability, Equity & Revenue Accounts:** Balance = $\sum \text{Credits} - \sum \text{Debits}$

## Consequences
- **Positive:** Mathematically verifiable audit logs. Complete prevention of phantom money creation.
- **Positive:** Zero IEEE 754 floating-point rounding errors.
- **Negative:** Computing balances on high-volume accounts requires aggregating postings. For large-scale accounts, snapshot rollups or caching layers are added to optimize query throughput.
