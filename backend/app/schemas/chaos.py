from typing import List, Dict, Any
from pydantic import BaseModel

class DuplicateStormRequest(BaseModel):
    concurrency_count: int = 100
    customer_id: str
    metric_name: str = "llm_tokens"
    quantity: int = 50000

class DuplicateStormResponse(BaseModel):
    concurrency_count: int
    idempotency_key: str
    unique_committed: int
    replays_blocked: int
    time_taken_ms: float
    message: str

class OverdraftRaceRequest(BaseModel):
    concurrency_count: int = 20
    customer_id: str
    charge_amount_cents: int = 1000 # $10.00 each
    initial_wallet_balance_cents: int = 5000 # $50.00 total prepaid

class OverdraftResultItem(BaseModel):
    task_index: int
    status: str # "COMMITTED" or "REJECTED_INSUFFICIENT_FUNDS"
    error: str = ""

class OverdraftRaceResponse(BaseModel):
    concurrency_count: int
    initial_balance_cents: int
    charges_attempted: int
    charges_succeeded: int
    charges_rejected: int
    final_balance_cents: int
    is_balance_valid: bool
    time_taken_ms: float
    results: List[OverdraftResultItem]
