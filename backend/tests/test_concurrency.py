import pytest
import asyncio
from backend.app.core.ledger_engine import LedgerEngine
from backend.app.schemas.chaos import OverdraftRaceRequest
from backend.app.api.v1.chaos import overdraft_race_test

@pytest.mark.asyncio
async def test_parallel_overdraft_race_condition(db_session):
    """
    Spawns 20 concurrent transactions firing $10 charges against a $50 balance.
    With SELECT ... FOR UPDATE row-level locking:
    - Exactly 5 charges succeed ($50 total).
    - Exactly 15 charges fail cleanly with InsufficientFunds.
    - Final balance is verified to be exactly $0.00 (NEVER negative).
    - Global ledger remains in balance (delta == 0).
    """
    req = OverdraftRaceRequest(
        concurrency_count=20,
        customer_id="cus_quantum_labs",
        charge_amount_cents=1000, # $10.00
        initial_wallet_balance_cents=5000 # $50.00
    )

    resp = await overdraft_race_test(req)

    assert resp.concurrency_count == 20
    assert resp.charges_succeeded == 5
    assert resp.charges_rejected == 15
    assert resp.final_balance_cents == 0
    assert resp.is_balance_valid is True

    # Global ledger check
    proof = await LedgerEngine.verify_global_ledger(db_session)
    assert proof["is_balanced"] is True
    assert proof["delta_cents"] == 0
