from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.types import JSON
from backend.app.database import Base

class IdempotencyRecord(Base):
    """
    Stripe-grade API Idempotency Record.
    Tracks requests by key, compares SHA256 of payload, locks in-flight requests,
    and returns cached response on idempotent re-execution.
    """
    __tablename__ = "idempotency_records"

    key = Column(String(128), primary_key=True, index=True)
    path = Column(String(256), nullable=False)
    request_hash = Column(String(64), nullable=False) # SHA-256 hex digest
    status = Column(String(32), nullable=False, default="PROCESSING") # "PROCESSING", "SUCCEEDED", "FAILED"
    status_code = Column(Integer, nullable=True)
    response_body = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
