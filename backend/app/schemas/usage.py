from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class MeterEventCreate(BaseModel):
    event_id: str = Field(..., description="Unique event idempotency key")
    customer_id: str
    subscription_id: Optional[str] = None
    metric_name: str = Field(..., description="e.g. llm_tokens, gpu_seconds")
    quantity: int = Field(gt=0, description="Usage quantity integer")
    timestamp: datetime = Field(..., description="Virtual clock timestamp of event")

class MeterEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    subscription_id: Optional[str] = None
    metric_name: str
    quantity: int
    timestamp: datetime
    idempotency_key: str
    is_replayed: bool = False
    invoice_id: Optional[str] = None
    created_at: datetime
