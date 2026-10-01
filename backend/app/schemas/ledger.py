from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.ledger import AccountType, PostingDirection

class PostingCreate(BaseModel):
    account_id: str
    direction: PostingDirection
    amount_cents: int = Field(gt=0, description="Amount in integer cents (must be > 0)")

class PostingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    journal_entry_id: str
    account_id: str
    direction: PostingDirection
    amount_cents: int
    created_at: datetime

class JournalEntryCreate(BaseModel):
    description: str
    effective_at: datetime
    postings: List[PostingCreate]
    idempotency_key: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None

class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    idempotency_key: Optional[str] = None
    description: str
    effective_at: datetime
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    postings: List[PostingResponse]

class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: AccountType
    currency: str
    description: Optional[str] = None
    balance_cents: int
    created_at: datetime

class GlobalLedgerVerificationResponse(BaseModel):
    total_debits_cents: int
    total_credits_cents: int
    delta_cents: int
    is_balanced: bool
    total_journal_entries: int
    total_postings: int
    proof_formula: str
