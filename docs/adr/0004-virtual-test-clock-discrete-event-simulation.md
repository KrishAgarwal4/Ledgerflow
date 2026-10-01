# ADR 0004: Virtual Test Clock Architecture & Discrete Event Simulation

## Status
Accepted

## Context
Testing subscription billing, tier proration, and dunning retry loops in traditional environments is exceptionally difficult. Engineering teams often resort to mocking `datetime.now()`, using system sleep delays, or manually setting dates in database tables. These approaches fail to test complex state transitions (e.g. 3-step dunning retry backoff or mid-cycle upgrades) under realistic chronological conditions.

## Decision
We implement a **Deterministic Virtual Test Clock** inspired by Stripe Billing Test Clocks:
1. **No System Clocks in Domain Logic:** All domain logic and billing calculations accept an explicit `virtual_now` timestamp read from the `test_clocks` table.
2. **Discrete Event Simulation (DES):**
   When `advance_clock(target_time)` is invoked, rather than running a naive fixed-interval tick loop, Chronos determines the earliest upcoming scheduled event:
   $$t_{\text{next}} = \min(\{t \mid t \in \text{ScheduledMilestones} \land t_{\text{current}} < t \le t_{\text{target}}\})$$
   Chronos leaps virtual time directly to $t_{\text{next}}$, executes all due events (cycle rollover, invoice settlement, dunning retry), records an immutable audit log in `clock_milestones`, flushes state, and repeats.
3. **Exact-Second Proration Mathematics:**
   For mid-cycle tier changes at $t_{\text{change}}$ between $t_{\text{start}}$ and $t_{\text{end}}$:
   $$\text{TotalSeconds} = t_{\text{end}} - t_{\text{start}}$$
   $$\text{RemainingSeconds} = t_{\text{end}} - t_{\text{change}}$$
   $$\text{RefundCreditCents} = \left\lfloor \text{OldBaseFee} \times \frac{\text{RemainingSeconds}}{\text{TotalSeconds}} \right\rfloor$$
   $$\text{NewChargeCents} = \left\lfloor \text{NewBaseFee} \times \frac{\text{RemainingSeconds}}{\text{TotalSeconds}} \right\rfloor$$
   $$\text{NetAdjustment} = \text{NewChargeCents} - \text{RefundCreditCents}$$
4. **Smart Retries & Dunning State Machine:**
   If invoice collection fails:
   $$\text{Schedule} = [+1\text{ day}, +3\text{ days}, +7\text{ days}]$$
   - Attempt 1 failure $\rightarrow$ `PAST_DUE`, retry scheduled $+1\text{d}$.
   - Attempt 2 failure $\rightarrow$ `PAST_DUE`, retry scheduled $+3\text{d}$.
   - Attempt 3 failure $\rightarrow$ `CANCELED`, invoice `UNCOLLECTIBLE`, automatic bad debt expense write-off.

## Consequences
- **Positive:** Enables instantaneous deterministic simulation of 1 year of billing in $<200\text{ms}$.
- **Positive:** Mathematically accurate down-to-the-second proration credits and debits.
- **Negative:** Requires strict discipline across codebase to ensure no module calls `datetime.now()` directly.
