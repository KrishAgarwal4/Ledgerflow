from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
import enum
from backend.app.database import Base

class PaymentMethodStatus(str, enum.Enum):
    VALID = "VALID"
    FAIL_ALWAYS = "FAIL_ALWAYS"  # For simulating dunning/payment retry failure states

class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(64), primary_key=True, index=True) # e.g. "cus_deepmind_01"
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, unique=True, index=True)
    currency = Column(String(8), nullable=False, default="usd")
    
    # Linked Double-Entry Accounts
    wallet_account_id = Column(String(64), ForeignKey("accounts.id"), nullable=False)
    receivable_account_id = Column(String(64), ForeignKey("accounts.id"), nullable=False)
    
    payment_method_status = Column(
        Enum(PaymentMethodStatus, name="payment_method_status"),
        default=PaymentMethodStatus.VALID,
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    wallet_account = relationship("Account", foreign_keys=[wallet_account_id])
    receivable_account = relationship("Account", foreign_keys=[receivable_account_id])
    subscriptions = relationship("Subscription", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")
    usage_events = relationship("UsageEvent", back_populates="customer")
