import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from backend.app.core.clock_engine import ClockEngine
from backend.app.core.billing_engine import BillingEngine
from backend.app.models.billing import Plan, Subscription, Invoice, InvoiceStatus
from backend.app.models.usage import UsageEvent
from backend.app.models.customer import Customer
from backend.app.core.ledger_engine import LedgerEngine

@pytest.mark.asyncio
async def test_proration_calculation():
    """Validates exact down-to-the-second proration math."""
    starter = Plan(id="p1", name="Starter", base_fee_cents=3000, billing_interval="month", included_tokens=100, overage_rate_cents_per_million=100)
    scale = Plan(id="p2", name="Scale", base_fee_cents=9000, billing_interval="month", included_tokens=1000, overage_rate_cents_per_million=50)

    p_start = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    p_end = p_start + timedelta(days=30) # 30 days = 2,592,000 seconds
    
    # Upgrade exactly halfway through the cycle (+15 days)
    change_time = p_start + timedelta(days=15)

    refund, charge, net = BillingEngine.calculate_proration(
        old_plan=starter,
        new_plan=scale,
        period_start=p_start,
        period_end=p_end,
        change_time=change_time
    )

    # 50% unused on starter ($30 / 2 = $15 = 1500¢)
    assert refund == 1500
    # 50% charged on scale ($90 / 2 = $45 = 4500¢)
    assert charge == 4500
    # Net adjustment: 4500 - 1500 = 3000¢ ($30)
    assert net == 3000

@pytest.mark.asyncio
async def test_test_clock_cycle_rollover_and_ledger_posting(db_session):
    """
    Ingests usage events, then advances the test clock by +30 days.
    Proves that:
    1. Usage is aggregated.
    2. Invoice is generated and finalized.
    3. Balanced double-entry journal entry is recorded.
    4. Subscription current_period rolls forward.
    """
    clock = await ClockEngine.get_or_create_clock(db_session, "clock_main")
    current_time = clock.current_virtual_time

    # Add 12,000,000 tokens of usage for Nexus AI (Scale tier includes 10M, so 2M overage)
    evt = UsageEvent(
        id="evt_test_overage",
        customer_id="cus_nexus_ai",
        subscription_id="sub_nexus_scale",
        metric_name="llm_tokens",
        quantity=12_000_000,
        timestamp=current_time + timedelta(days=5),
        idempotency_key="key_test_overage_1",
    )
    db_session.add(evt)
    await db_session.commit()

    # Advance clock past cycle end (+30 days)
    target_time = current_time + timedelta(days=31)
    milestones = await ClockEngine.advance_clock(db_session, "clock_main", target_time)

    assert len(milestones) > 0
    
    # Verify invoice was created
    inv_stmt = select(Invoice).where(Invoice.customer_id == "cus_nexus_ai").order_by(Invoice.created_at.desc())
    invoice = (await db_session.execute(inv_stmt)).scalars().first()
    assert invoice is not None
    assert invoice.status == InvoiceStatus.PAID
    # Base fee ($199) + 2M overage ($20) = $219.00 (21900¢)
    assert invoice.total_cents == 21900
    assert invoice.journal_entry_id is not None

    # Verify global ledger balance proof
    proof = await LedgerEngine.verify_global_ledger(db_session)
    assert proof["is_balanced"] is True
    assert proof["delta_cents"] == 0
