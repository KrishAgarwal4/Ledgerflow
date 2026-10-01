# ADR 0003: Distributed Idempotency Protocol & SHA-256 Fingerprinting

## Status
Accepted

## Context
In distributed payment and usage metering systems, network partitions and gateway timeouts frequently cause clients to retry requests. If a request was processed by the server but the response was dropped over the wire, a naive retry would process the transaction a second time, resulting in double-charges.

## Decision
We implement a Stripe-grade **Two-Phase Idempotency Protocol**:
1. **Idempotency Key Specification:** Clients provide a unique key via the `Idempotency-Key` HTTP header or the body parameter `event_id`.
2. **SHA-256 Parameter Fingerprinting:** The request path and normalized JSON payload are hashed:
   $$\text{request\_hash} = \text{SHA256}(\text{path} + \text{canonical\_json}(\text{payload}))$$
3. **Atomic Mutual Exclusion:**
   - When a request arrives, Chronos initiates an autonomous database transaction claiming the key in `idempotency_records` with status `PROCESSING`.
   - If two identical requests arrive simultaneously, PostgreSQL's primary key constraint serializes them: the winner proceeds, and the concurrent worker catches `UniqueViolationError`, returning `409 Conflict`.
4. **Result Caching & Replay:**
   - Once execution completes, the record transitions to `SUCCEEDED` storing `status_code` and `response_body`.
   - Subsequent requests with the same key and identical hash bypass business logic and immediately return the cached response with:
     `X-Idempotent-Replayed: true`
5. **Tamper Detection:**
   - If an existing key is reused with differing parameters, Chronos detects the mismatch ($\text{hash}_{\text{stored}} \neq \text{hash}_{\text{new}}$) and rejects with `422 Unprocessable Entity` ("Idempotency key reused with different request parameters").

## Consequences
- **Positive:** Zero risk of duplicate billing under network replay storms.
- **Positive:** Clients can safely retry with exponential backoff without custom client-side reconciliation.
- **Negative:** Storage overhead for idempotency logs, requiring a time-to-live (TTL) retention policy in large-scale deployments.
