import enum
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from backend.app.database import Base

class ClockStatus(str, enum.Enum):
    READY = "READY"
    ADVANCING = "ADVANCING"

class TestClock(Base):
    __tablename__ = "test_clocks"

    id = Column(String(64), primary_key=True, index=True) # e.g. "clock_main"
    name = Column(String(128), nullable=False)
    current_virtual_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(ClockStatus, name="clock_status"), default=ClockStatus.READY, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    milestones = relationship("ClockMilestone", back_populates="clock", cascade="all, delete-orphan", order_by="desc(ClockMilestone.timestamp)")

class ClockMilestone(Base):
    """Audit log of discrete events simulated as TestClock advanced through time."""
    __tablename__ = "clock_milestones"

    id = Column(String(64), primary_key=True, index=True)
    clock_id = Column(String(64), ForeignKey("test_clocks.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True) # Time at which event was triggered
    event_type = Column(String(64), nullable=False, index=True) # "CYCLE_ROLLOVER", "DUNNING_RETRY", "TIER_PRORATION", etc.
    description = Column(String(256), nullable=False)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    clock = relationship("TestClock", back_populates="milestones")
