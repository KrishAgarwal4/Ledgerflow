import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, Integer, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.app.database import Base

class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    INCOMPLETE = "INCOMPLETE"

class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    PAID = "PAID"
    UNCOLLECTIBLE = "UNCOLLECTIBLE"
    VOID = "VOID"

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(64), primary_key=True, index=True) # e.g. "plan_ai_starter"
    name = Column(String(128), nullable=False)
    billing_interval = Column(String(32), nullable=False, default="month")
    base_fee_cents = Column(BigInteger, nullable=False, default=0) # Base monthly fee
    included_tokens = Column(BigInteger, nullable=False, default=1_000_000) # Included usage
    overage_rate_cents_per_million = Column(BigInteger, nullable=False, default=2000) # $20.00 / 1M tokens overage
    currency = Column(String(8), nullable=False, default="usd")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    subscriptions = relationship("Subscription", back_populates="plan")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(64), primary_key=True, index=True) # e.g. "sub_01j7h..."
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    plan_id = Column(String(64), ForeignKey("plans.id"), nullable=False, index=True)
    status = Column(
        Enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.ACTIVE,
        nullable=False
    )
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    
    # Dunning state machine tracking
    dunning_attempt_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    invoices = relationship("Invoice", back_populates="subscription")
    usage_events = relationship("UsageEvent", back_populates="subscription")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(64), primary_key=True, index=True) # e.g. "in_01j7h..."
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    subscription_id = Column(String(64), ForeignKey("subscriptions.id"), nullable=True, index=True)
    status = Column(
        Enum(InvoiceStatus, name="invoice_status"),
        default=InvoiceStatus.OPEN,
        nullable=False
    )
    subtotal_cents = Column(BigInteger, nullable=False, default=0)
    tax_cents = Column(BigInteger, nullable=False, default=0)
    total_cents = Column(BigInteger, nullable=False, default=0)
    amount_paid_cents = Column(BigInteger, nullable=False, default=0)
    amount_remaining_cents = Column(BigInteger, nullable=False, default=0)
    
    due_date = Column(DateTime(timezone=True), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    
    # Linked Journal Entry for the revenue recognition & accounts receivable posting
    journal_entry_id = Column(String(64), ForeignKey("journal_entries.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    customer = relationship("Customer", back_populates="invoices")
    subscription = relationship("Subscription", back_populates="invoices")
    journal_entry = relationship("JournalEntry", foreign_keys=[journal_entry_id])
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")

class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(64), primary_key=True, index=True)
    invoice_id = Column(String(64), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(256), nullable=False)
    quantity = Column(BigInteger, nullable=False, default=1)
    unit_amount_cents = Column(BigInteger, nullable=False, default=0)
    amount_cents = Column(BigInteger, nullable=False, default=0)
    proration = Column(Boolean, default=False, nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)

    invoice = relationship("Invoice", back_populates="line_items")
