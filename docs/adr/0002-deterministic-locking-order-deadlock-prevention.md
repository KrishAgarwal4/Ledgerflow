# ADR 0002: Deterministic Lock Hierarchy for Deadlock Prevention

## Status
Accepted

## Context
When multiple concurrent database transactions attempt to lock the same resources in differing order, a circular wait condition occurs:
- Transaction 1 holds a lock on Account $A$ and requests a lock on Account $B$.
- Transaction 2 holds a lock on Account $B$ and requests a lock on Account $A$.
Both transactions block indefinitely until the database detects a deadlock and forcibly aborts one of them. In high-frequency billing systems (e.g. usage surges, subscription renewals), lock contention causes elevated error rates and transaction retries.

## Decision
We implement a **Deterministic Lock Hierarchy** across all ledger operations:
1. Whenever a transaction touches multiple accounts, the list of unique `account_id`s is extracted and sorted in strict lexicographical ascending order:
   ```python
   unique_account_ids = sorted(list(set(p["account_id"] for p in postings)))
   ```
2. Row locks are acquired in this exact sorted order using:
   ```sql
   SELECT id FROM accounts WHERE id IN (...) ORDER BY id ASC FOR UPDATE;
   ```
3. Balance assertions (such as verifying prepaid wallet solvency) are evaluated *after* acquiring locks, ensuring serialized consistency.

## Mathematical Proof of Deadlock Freedom
Let $\mathcal{A} = \{a_1, a_2, \dots, a_n\}$ be the set of all account identifiers equipped with standard lexicographical total ordering $<$.
1. Suppose a deadlock exists. By the Coffman conditions, there must exist a directed cycle in the resource allocation graph:
   $$T_1 \rightarrow a_{i_1} \rightarrow T_2 \rightarrow a_{i_2} \rightarrow \dots \rightarrow T_k \rightarrow a_{i_k} \rightarrow T_1$$
2. Since every transaction $T_j$ acquires locks strictly in ascending order ($a_{i_1} < a_{i_2} < \dots < a_{i_k}$), the cycle implies:
   $$a_{i_1} < a_{i_2} < \dots < a_{i_k} < a_{i_1}$$
3. By the irreflexive and transitive properties of total ordering, $a_{i_1} < a_{i_1}$ is a contradiction.
4. Therefore, no cycle can form, and deadlocks are mathematically impossible.

## Consequences
- **Positive:** Complete elimination of deadlock aborts under high-concurrency bursts.
- **Positive:** Reliable execution of parallel overdraft limits (e.g. 20 concurrent spends against 1 wallet).
- **Negative:** Minor sorting overhead $O(k \log k)$ where $k \le 10$ is the number of accounts per journal entry (negligible in practice).
