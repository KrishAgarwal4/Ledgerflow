from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.models.clock import ClockStatus

class ClockAdvanceRequest(BaseModel):
    target_time: Optional[datetime] = None
    advance_seconds: Optional[int] = Field(None, description="Advance relative to current virtual time (e.g. 3600 for 1 hr, 86400 for 1 day, 2592000 for 30 days)")

class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    clock_id: str
    timestamp: datetime
    event_type: str
    description: str
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime

class ClockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    current_virtual_time: datetime
    status: ClockStatus
    milestones: List[MilestoneResponse] = []
