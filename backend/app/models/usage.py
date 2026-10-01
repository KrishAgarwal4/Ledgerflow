from datetime import datetime, timezone
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base

class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String(64), primary_key=True, index=True) # e.g. "evt_01j7h..."
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    subscription_id = Column(String(64), ForeignKey("subscriptions.id"), nullable=True, index=True)
    metric_name = Column(String(64), nullable=False, index=True) # e.g. "llm_tokens", "gpu_seconds"
    quantity = Column(BigInteger, nullable=False) # e.g. 250,000 tokens
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True) # Virtual clock time
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    invoice_id = Column(String(64), ForeignKey("invoices.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    customer = relationship("Customer", back_populates="usage_events")
    subscription = relationship("Subscription", back_populates="usage_events")
    invoice = relationship("Invoice")

    __table_args__ = (
        Index("idx_usage_customer_metric_billed", "customer_id", "metric_name", "invoice_id"),
    )
