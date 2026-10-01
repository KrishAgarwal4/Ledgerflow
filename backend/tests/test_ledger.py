import pytest
from datetime import datetime, timezone
from backend.app.core.ledger_engine import (
    LedgerEngine, ZeroSumViolationError, InsufficientFundsError,
    PLATFORM_CASH_ACCOUNT_ID, PLATFORM_REVENUE_ACCOUNT_ID
)
from backend.app.models.ledger import PostingDirection

@pytest.mark.asyncio
async def test_zero_sum_enforcement(db_session):
    """Proves that unbalanced journal entries are rejected immediately."""
    virtual_now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Attempt unbalanced entry: DEBIT 5000, CREDIT 4000 (Delta: 1000)
    with pytest.raises(ZeroSumViolationError) as exc_info:
        await LedgerEngine.create_journal_entry(
            session=db_session,
            description="Unbalanced Transaction Attempt",
            effective_at=virtual_now,
            postings=[
                {"account_id": PLATFORM_CASH_ACCOUNT_ID, "direction": PostingDirection.DEBIT, "amount_cents": 5000},
                {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.CREDIT, "amount_cents": 4000},
            ]
        )
    assert "Double-entry zero-sum invariant violated" in str(exc_info.value)
    assert exc_info.value.debit_sum == 5000
    assert exc_info.value.credit_sum == 4000

@pytest.mark.asyncio
async def test_positive_cents_enforcement(db_session):
    """Proves that zero or negative amounts are rejected."""
    virtual_now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(Exception):
        await LedgerEngine.create_journal_entry(
            session=db_session,
            description="Negative Cents Attempt",
            effective_at=virtual_now,
            postings=[
                {"account_id": PLATFORM_CASH_ACCOUNT_ID, "direction": PostingDirection.DEBIT, "amount_cents": -500},
                {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.CREDIT, "amount_cents": -500},
            ]
        )

@pytest.mark.asyncio
async def test_balanced_transaction_and_global_proof(db_session):
    """Proves balanced double-entry commits and preserves global mathematical balance."""
    virtual_now = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    # Execute valid balanced journal entry ($100 = 10,000 cents)
    entry = await LedgerEngine.create_journal_entry(
        session=db_session,
        description="Software License Sale",
        effective_at=virtual_now,
        postings=[
            {"account_id": PLATFORM_CASH_ACCOUNT_ID, "direction": PostingDirection.DEBIT, "amount_cents": 10000},
            {"account_id": PLATFORM_REVENUE_ACCOUNT_ID, "direction": PostingDirection.CREDIT, "amount_cents": 10000},
        ]
    )
    await db_session.commit()
    assert entry.id.startswith("jrn_")

    # Verify global ledger proof
    proof = await LedgerEngine.verify_global_ledger(db_session)
    assert proof["is_balanced"] is True
    assert proof["delta_cents"] == 0
    assert proof["total_debits_cents"] == proof["total_credits_cents"]
