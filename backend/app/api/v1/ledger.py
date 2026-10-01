from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db
from backend.app.models.ledger import Account, JournalEntry, LedgerPosting
from backend.app.schemas.ledger import (
    AccountResponse, JournalEntryCreate, JournalEntryResponse,
    GlobalLedgerVerificationResponse
)
from backend.app.core.ledger_engine import LedgerEngine, ZeroSumViolationError, InsufficientFundsError, AccountNotFoundError

router = APIRouter(prefix="/ledger", tags=["Ledger"])

@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts(session: AsyncSession = Depends(get_db)):
    """List all accounts with their real-time computed balances directly from postings."""
    stmt = select(Account).order_by(Account.type.asc(), Account.name.asc())
    accounts = (await session.execute(stmt)).scalars().all()

    results = []
    for acc in accounts:
        balance = await LedgerEngine.get_account_balance(session, acc.id)
        results.append(
            AccountResponse(
                id=acc.id,
                name=acc.name,
                type=acc.type,
                currency=acc.currency,
                description=acc.description,
                balance_cents=balance,
                created_at=acc.created_at,
            )
        )
    return results

@router.get("/journal-entries", response_model=List[JournalEntryResponse])
async def list_journal_entries(
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_db)
):
    """Retrieve immutable journal entries and their double-entry postings."""
    stmt = (
        select(JournalEntry)
        .order_by(JournalEntry.effective_at.desc(), JournalEntry.created_at.desc())
        .limit(limit)
    )
    entries = (await session.execute(stmt)).scalars().all()
    
    # Load postings eagerly
    for entry in entries:
        postings_stmt = select(LedgerPosting).where(LedgerPosting.journal_entry_id == entry.id)
        entry.postings = (await session.execute(postings_stmt)).scalars().all()

    return entries

@router.post("/journal-entries", response_model=JournalEntryResponse)
async def create_journal_entry(
    payload: JournalEntryCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Manually create a balanced journal entry.
    Fails immediately if SUM(DEBIT) != SUM(CREDIT).
    """
    try:
        postings_data = [
            {
                "account_id": p.account_id,
                "direction": p.direction,
                "amount_cents": p.amount_cents,
            }
            for p in payload.postings
        ]
        entry = await LedgerEngine.create_journal_entry(
            session=session,
            description=payload.description,
            effective_at=payload.effective_at,
            postings=postings_data,
            idempotency_key=payload.idempotency_key,
            metadata_json=payload.metadata_json,
        )
        await session.commit()

        # Reload with postings
        postings_stmt = select(LedgerPosting).where(LedgerPosting.journal_entry_id == entry.id)
        entry.postings = (await session.execute(postings_stmt)).scalars().all()
        return entry
    except ZeroSumViolationError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except (InsufficientFundsError, AccountNotFoundError) as e:
        await session.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record journal entry: {str(e)}")

@router.get("/verify", response_model=GlobalLedgerVerificationResponse)
async def verify_ledger(session: AsyncSession = Depends(get_db)):
    """
    Returns global mathematical proof that the entire ledger is in balance:
    SUM(DEBIT) - SUM(CREDIT) == 0.
    """
    return await LedgerEngine.verify_global_ledger(session)
