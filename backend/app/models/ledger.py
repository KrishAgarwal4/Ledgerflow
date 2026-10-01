import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, DateTime, Enum, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from backend.app.database import Base

class AccountType(str, enum.Enum):
    ASSET = "ASSET"          # e.g., Platform Cash, Accounts Receivable
    LIABILITY = "LIABILITY"  # e.g., Customer Prepaid Wallet / Unearned Revenue
    EQUITY = "EQUITY"        # Platform Retained Earnings
    REVENUE = "REVENUE"      # Usage Revenue, Subscription Revenue
    EXPENSE = "EXPENSE"      # Payment Processing Fees, Infrastructure Cost

class PostingDirection(str, enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(64), primary_key=True, index=True) # e.g. "acc_wallet_cus_01"
    name = Column(String(128), nullable=False)
    type = Column(Enum(AccountType, name="account_type"), nullable=False, index=True)
    currency = Column(String(8), nullable=False, default="usd")
    description = Column(String(256), nullable=True)
    is_active = Column(DateTime, nullable=True) # None if active, or timestamp when archived
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    postings = relationship("LedgerPosting", back_populates="account", cascade="all, delete-orphan")

class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(String(64), primary_key=True, index=True) # e.g. "jrn_01j7h8..."
    idempotency_key = Column(String(128), unique=True, index=True, nullable=True)
    description = Column(String(256), nullable=False)
    effective_at = Column(DateTime(timezone=True), nullable=False) # Tied to Virtual Clock
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    postings = relationship("LedgerPosting", back_populates="journal_entry", cascade="all, delete-orphan")

class LedgerPosting(Base):
    """
    Append-Only Ledger Posting.
    Invariants:
    1. Once inserted, NEVER updated or deleted.
    2. amount_cents > 0.
    3. Every JournalEntry must satisfy SUM(DEBIT) == SUM(CREDIT).
    """
    __tablename__ = "ledger_postings"

    id = Column(String(64), primary_key=True, index=True) # e.g. "pos_01j7h8..."
    journal_entry_id = Column(String(64), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String(64), ForeignKey("accounts.id"), nullable=False, index=True)
    direction = Column(Enum(PostingDirection, name="posting_direction"), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    account = relationship("Account", back_populates="postings")
    journal_entry = relationship("JournalEntry", back_populates="postings")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="chk_positive_posting_amount"),
        Index("idx_postings_acc_dir", "account_id", "direction"),
    )
