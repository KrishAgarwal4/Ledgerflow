from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.billing import SubscriptionStatus, InvoiceStatus
from backend.app.models.customer import PaymentMethodStatus

class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    billing_interval: str
    base_fee_cents: int
    included_tokens: int
    overage_rate_cents_per_million: int
    currency: str

class InvoiceLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    quantity: int
    unit_amount_cents: int
    amount_cents: int
    proration: bool
    period_start: datetime
    period_end: datetime

class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    subscription_id: Optional[str] = None
    status: InvoiceStatus
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    amount_paid_cents: int
    amount_remaining_cents: int
    due_date: datetime
    paid_at: Optional[datetime] = None
    period_start: datetime
    period_end: datetime
    journal_entry_id: Optional[str] = None
    created_at: datetime
    line_items: List[InvoiceLineItemResponse] = []

class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    dunning_attempt_count: int
    next_retry_at: Optional[datetime] = None
    created_at: datetime
    plan: Optional[PlanResponse] = None

class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    currency: str
    wallet_account_id: str
    receivable_account_id: str
    wallet_balance_cents: int
    receivable_balance_cents: int
    payment_method_status: PaymentMethodStatus
    active_subscription: Optional[SubscriptionResponse] = None
    created_at: datetime

class ChangePlanRequest(BaseModel):
    new_plan_id: str

class ProrationPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_plan_name: str
    new_plan_name: str
    refund_credit_cents: int
    new_charge_cents: int
    net_adjustment_cents: int
    period_start: datetime
    period_end: datetime
    change_time: datetime
