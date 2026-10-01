from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.clock import TestClock, ClockMilestone, ClockStatus
from backend.app.models.billing import Subscription, SubscriptionStatus, Invoice
from backend.app.core.billing_engine import BillingEngine
from backend.app.core.dunning_engine import DunningEngine
from backend.app.core.ledger_engine import generate_id

class ClockAdvancementError(Exception):
    pass

class ClockEngine:
    @staticmethod
    async def get_or_create_clock(
        session: AsyncSession,
        clock_id: str = "clock_main",
        initial_time: Optional[datetime] = None
    ) -> TestClock:
        query = select(TestClock).where(TestClock.id == clock_id).with_for_update()
        clock = (await session.execute(query)).scalar_one_or_none()
        if not clock:
            if not initial_time:
                initial_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
            clock = TestClock(
                id=clock_id,
                name="Production Simulation Clock",
                current_virtual_time=initial_time,
                status=ClockStatus.READY,
            )
            session.add(clock)
            await session.commit()
        return clock

    @staticmethod
    async def advance_clock(
        session: AsyncSession,
        clock_id: str,
        target_time: datetime
    ) -> List[ClockMilestone]:
        """
        Advances the virtual clock to target_time by deterministically simulating
        all intervening events in exact chronological sequence.
        Processes ALL subscriptions matching milestones at each discrete timestamp.
        """
        clock_stmt = select(TestClock).where(TestClock.id == clock_id).with_for_update()
        clock = (await session.execute(clock_stmt)).scalar_one_or_none()
        if not clock:
            raise ClockAdvancementError(f"TestClock {clock_id} not found.")

        if target_time <= clock.current_virtual_time:
            raise ClockAdvancementError(
                f"Target virtual time ({target_time.isoformat()}) must be strictly in the future of current clock time ({clock.current_virtual_time.isoformat()})."
            )

        clock.status = ClockStatus.ADVANCING
        await session.flush()

        executed_milestones: List[ClockMilestone] = []

        max_safety_iterations = 500
        iteration = 0

        while clock.current_virtual_time < target_time and iteration < max_safety_iterations:
            iteration += 1

            # Find the earliest cycle end among all active/past_due subscriptions
            cycle_stmt = (
                select(func.min(Subscription.current_period_end))
                .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]))
                .where(Subscription.current_period_end > clock.current_virtual_time)
                .where(Subscription.current_period_end <= target_time)
            )
            earliest_cycle = (await session.execute(cycle_stmt)).scalar_one_or_none()

            # Find the earliest dunning retry among all past_due subscriptions
            dunning_stmt = (
                select(func.min(Subscription.next_retry_at))
                .where(Subscription.next_retry_at.is_not(None))
                .where(Subscription.next_retry_at > clock.current_virtual_time)
                .where(Subscription.next_retry_at <= target_time)
            )
            earliest_dunning = (await session.execute(dunning_stmt)).scalar_one_or_none()

            candidates = [t for t in [earliest_cycle, earliest_dunning] if t is not None]
            if not candidates:
                # No more discrete milestones before target_time
                clock.current_virtual_time = target_time
                break

            next_event_time = min(candidates)
            clock.current_virtual_time = next_event_time

            # 1. Process all period rollovers due at next_event_time
            if earliest_cycle == next_event_time:
                due_subs_query = (
                    select(Subscription)
                    .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]))
                    .where(Subscription.current_period_end == next_event_time)
                    .with_for_update()
                )
                due_subs = (await session.execute(due_subs_query)).scalars().all()

                for sub in due_subs:
                    invoice, payment_status = await BillingEngine.finalize_billing_cycle(
                        session=session,
                        subscription_id=sub.id,
                        virtual_now=next_event_time
                    )

                    if payment_status in ("PAYMENT_SUCCEEDED", "PAID_ZERO_BALANCE"):
                        sub.current_period_start = next_event_time
                        sub.current_period_end = next_event_time + timedelta(days=30)
                        ms = ClockMilestone(
                            id=generate_id("ms"),
                            clock_id=clock.id,
                            timestamp=next_event_time,
                            event_type="CYCLE_ROLLOVER_PAID",
                            description=f"Cycle closed & Invoice {invoice.id} paid (${invoice.total_cents/100:.2f})",
                            details_json={
                                "subscription_id": sub.id,
                                "invoice_id": invoice.id,
                                "total_cents": invoice.total_cents,
                                "payment_status": payment_status,
                                "next_period_end": sub.current_period_end.isoformat(),
                            },
                        )
                    else:
                        dunning_info = await DunningEngine.process_failed_payment(
                            session=session,
                            subscription=sub,
                            invoice=invoice,
                            virtual_now=next_event_time
                        )
                        ms = ClockMilestone(
                            id=generate_id("ms"),
                            clock_id=clock.id,
                            timestamp=next_event_time,
                            event_type="CYCLE_ROLLOVER_PAYMENT_FAILED",
                            description=f"Cycle closed, Invoice {invoice.id} unpaid (${invoice.total_cents/100:.2f}). Entered PAST_DUE",
                            details_json={
                                "subscription_id": sub.id,
                                "invoice_id": invoice.id,
                                "total_cents": invoice.total_cents,
                                "dunning_info": dunning_info,
                            },
                        )

                    session.add(ms)
                    executed_milestones.append(ms)

            # 2. Process all dunning retries due at next_event_time
            if earliest_dunning == next_event_time:
                due_retries_query = (
                    select(Subscription)
                    .where(Subscription.next_retry_at == next_event_time)
                    .with_for_update()
                )
                due_retries = (await session.execute(due_retries_query)).scalars().all()

                for sub in due_retries:
                    retry_result = await DunningEngine.execute_dunning_retry(
                        session=session,
                        subscription_id=sub.id,
                        virtual_now=next_event_time
                    )
                    action = retry_result.get("action", "DUNNING_RETRY")
                    desc = (
                        f"Dunning retry #{retry_result.get('attempt')}: {action} (Status: {retry_result.get('subscription_status')})"
                    )
                    ms = ClockMilestone(
                        id=generate_id("ms"),
                        clock_id=clock.id,
                        timestamp=next_event_time,
                        event_type=f"DUNNING_{action}",
                        description=desc,
                        details_json=retry_result,
                    )
                    session.add(ms)
                    executed_milestones.append(ms)

            # Flush all model updates so subsequent queries see new next_retry_at and period_end
            await session.flush()

        clock.current_virtual_time = target_time
        clock.status = ClockStatus.READY
        await session.commit()
        return executed_milestones
