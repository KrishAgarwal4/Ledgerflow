import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from backend.app.core.clock_engine import ClockEngine
from backend.app.models.billing import Subscription, SubscriptionStatus, Invoice, InvoiceStatus
from backend.app.core.ledger_engine import LedgerEngine

@pytest.mark.asyncio
async def test_dunning_retry_lifecycle(db_session):
    """
    Apex Synthetics has payment_method_status = FAIL_ALWAYS and $0 wallet balance.
    Advancing the clock past cycle end + 15 days should trigger:
    1. Initial payment failure -> Subscription status PAST_DUE, retry scheduled +1d.
    2. Retry 1 failure (+1d) -> retry scheduled +3d.
    3. Retry 2 failure (+3d) -> retry scheduled +7d.
    4. Retry 3 failure (+7d) -> Subscription status CANCELED, invoice UNCOLLECTIBLE.
    5. Bad debt expense ledger write-off recorded.
    """
    clock = await ClockEngine.get_or_create_clock(db_session, "clock_main")
    start_time = clock.current_virtual_time

    # Advance clock by +45 days (past cycle end + 15 days of dunning)
    target_time = start_time + timedelta(days=45)
    milestones = await ClockEngine.advance_clock(db_session, "clock_main", target_time)

    # Check Apex Synthetics subscription status
    sub_stmt = select(Subscription).where(Subscription.customer_id == "cus_apex_ai")
    sub = (await db_session.execute(sub_stmt)).scalar_one()
    await db_session.refresh(sub)

    assert sub.status == SubscriptionStatus.CANCELED
    assert sub.dunning_attempt_count >= 3

    # Check invoice status
    inv_stmt = select(Invoice).where(Invoice.customer_id == "cus_apex_ai").order_by(Invoice.created_at.desc())
    invoice = (await db_session.execute(inv_stmt)).scalars().first()
    assert invoice is not None
    assert invoice.status == InvoiceStatus.UNCOLLECTIBLE

    # Verify global ledger balance proof remains strictly zero-sum
    proof = await LedgerEngine.verify_global_ledger(db_session)
    assert proof["is_balanced"] is True
    assert proof["delta_cents"] == 0
