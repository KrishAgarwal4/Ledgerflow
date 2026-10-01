from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.ledger import Account, AccountType, JournalEntry, LedgerPosting, PostingDirection

class LedgerError(Exception):
    pass

class ZeroSumViolationError(LedgerError):
    def __init__(self, debit_sum: int, credit_sum: int):
        self.debit_sum = debit_sum
        self.credit_sum = credit_sum
        super().__init__(
            f"Double-entry zero-sum invariant violated: Total DEBIT ({debit_sum}¢) != Total CREDIT ({credit_sum}¢). Delta: {debit_sum - credit_sum}¢."
        )

class InsufficientFundsError(LedgerError):
    def __init__(self, account_id: str, available_cents: int, requested_cents: int):
        self.account_id = account_id
        self.available_cents = available_cents
        self.requested_cents = requested_cents
        super().__init__(
            f"Account '{account_id}' has insufficient balance: available {available_cents}¢, requested {requested_cents}¢."
        )

class AccountNotFoundError(LedgerError):
    def __init__(self, account_id: str):
        super().__init__(f"Ledger account '{account_id}' not found.")

PLATFORM_REVENUE_ACCOUNT_ID = "acc_platform_revenue"
PLATFORM_CASH_ACCOUNT_ID = "acc_platform_cash"

def generate_id(prefix: str) -> str:
    """Generate Stripe-style unique prefixed ID."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"

class LedgerEngine:
    @staticmethod
    async def get_account_balance(session: AsyncSession, account_id: str) -> int:
        """
        Computes real-time account balance directly from immutable ledger postings.
        ASSET, EXPENSE: Debit - Credit
        LIABILITY, EQUITY, REVENUE: Credit - Debit
        """
        account_query = select(Account).where(Account.id == account_id)
        account = (await session.execute(account_query)).scalar_one_or_none()
        if not account:
            raise AccountNotFoundError(account_id)

        # Sum DEBITs
        debit_query = (
            select(func.coalesce(func.sum(LedgerPosting.amount_cents), 0))
            .where(LedgerPosting.account_id == account_id)
            .where(LedgerPosting.direction == PostingDirection.DEBIT)
        )
        total_debits = (await session.execute(debit_query)).scalar_one()

        # Sum CREDITs
        credit_query = (
            select(func.coalesce(func.sum(LedgerPosting.amount_cents), 0))
            .where(LedgerPosting.account_id == account_id)
            .where(LedgerPosting.direction == PostingDirection.CREDIT)
        )
        total_credits = (await session.execute(credit_query)).scalar_one()

        if account.type in (AccountType.ASSET, AccountType.EXPENSE):
            return int(total_debits - total_credits)
        else: # LIABILITY, EQUITY, REVENUE
            return int(total_credits - total_debits)

    @staticmethod
    async def create_journal_entry(
        session: AsyncSession,
        description: str,
        effective_at: datetime,
        postings: List[Dict[str, Any]], # [{"account_id": ..., "direction": "DEBIT"|"CREDIT", "amount_cents": ...}]
        idempotency_key: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
        enforce_non_negative_accounts: Optional[List[str]] = None,
    ) -> JournalEntry:
        """
        Atomically records a balanced JournalEntry with postings.
        Guarantees:
        1. Strict Zero-Sum: SUM(DEBIT) == SUM(CREDIT).
        2. Deterministic Lock Ordering: locks all affected accounts in ASC order via SELECT ... FOR UPDATE.
        3. No negative balances for specified accounts (e.g. prepaid wallet).
        """
        if not postings:
            raise LedgerError("Journal entry must contain at least two postings.")

        # 1. Zero-Sum validation
        total_debit = 0
        total_credit = 0
        for p in postings:
            amount = int(p["amount_cents"])
            if amount <= 0:
                raise LedgerError(f"Posting amount must be strictly positive integer cents. Received: {amount}")
            
            direction = p["direction"]
            if isinstance(direction, str):
                direction = PostingDirection(direction)

            if direction == PostingDirection.DEBIT:
                total_debit += amount
            elif direction == PostingDirection.CREDIT:
                total_credit += amount
            else:
                raise LedgerError(f"Invalid posting direction: {direction}")

        if total_debit != total_credit:
            raise ZeroSumViolationError(total_debit, total_credit)

        # 2. Deterministic Row-Level Lock Ordering
        unique_account_ids = sorted(list(set(p["account_id"] for p in postings)))
        lock_stmt = (
            select(Account)
            .where(Account.id.in_(unique_account_ids))
            .order_by(Account.id.asc())
            .with_for_update()
        )
        locked_accounts_res = await session.execute(lock_stmt)
        locked_accounts = {acc.id: acc for acc in locked_accounts_res.scalars().all()}

        for acc_id in unique_account_ids:
            if acc_id not in locked_accounts:
                raise AccountNotFoundError(acc_id)

        # 3. Check non-negative constraints (e.g., customer prepaid wallet)
        if enforce_non_negative_accounts:
            for acc_id in enforce_non_negative_accounts:
                current_bal = await LedgerEngine.get_account_balance(session, acc_id)
                # Calculate net change for this account in this entry
                acc = locked_accounts[acc_id]
                net_change = 0
                for p in postings:
                    if p["account_id"] == acc_id:
                        p_dir = PostingDirection(p["direction"]) if isinstance(p["direction"], str) else p["direction"]
                        amt = int(p["amount_cents"])
                        if acc.type in (AccountType.ASSET, AccountType.EXPENSE):
                            net_change += amt if p_dir == PostingDirection.DEBIT else -amt
                        else: # LIABILITY, EQUITY, REVENUE
                            net_change += amt if p_dir == PostingDirection.CREDIT else -amt

                if current_bal + net_change < 0:
                    raise InsufficientFundsError(acc_id, current_bal, abs(net_change))

        # 4. Insert Journal Entry & Postings
        entry_id = generate_id("jrn")
        journal_entry = JournalEntry(
            id=entry_id,
            idempotency_key=idempotency_key,
            description=description,
            effective_at=effective_at,
            metadata_json=metadata_json or {},
        )
        session.add(journal_entry)
        await session.flush()

        for p in postings:
            direction = PostingDirection(p["direction"]) if isinstance(p["direction"], str) else p["direction"]
            posting = LedgerPosting(
                id=generate_id("pos"),
                journal_entry_id=entry_id,
                account_id=p["account_id"],
                direction=direction,
                amount_cents=int(p["amount_cents"]),
            )
            session.add(posting)

        await session.flush()
        return journal_entry

    @staticmethod
    async def verify_global_ledger(session: AsyncSession) -> Dict[str, Any]:
        """
        Global mathematical proof that every posting in the system balances to zero.
        SUM(all DEBITs) - SUM(all CREDITs) === 0
        """
        debit_query = select(func.coalesce(func.sum(LedgerPosting.amount_cents), 0)).where(
            LedgerPosting.direction == PostingDirection.DEBIT
        )
        credit_query = select(func.coalesce(func.sum(LedgerPosting.amount_cents), 0)).where(
            LedgerPosting.direction == PostingDirection.CREDIT
        )
        total_debits = int((await session.execute(debit_query)).scalar_one())
        total_credits = int((await session.execute(credit_query)).scalar_one())
        delta = total_debits - total_credits

        entry_count_query = select(func.count(JournalEntry.id))
        posting_count_query = select(func.count(LedgerPosting.id))
        total_entries = int((await session.execute(entry_count_query)).scalar_one())
        total_postings = int((await session.execute(posting_count_query)).scalar_one())

        return {
            "total_debits_cents": total_debits,
            "total_credits_cents": total_credits,
            "delta_cents": delta,
            "is_balanced": (delta == 0),
            "total_journal_entries": total_entries,
            "total_postings": total_postings,
            "proof_formula": "SUM(DEBITS) - SUM(CREDITS) == 0",
        }
