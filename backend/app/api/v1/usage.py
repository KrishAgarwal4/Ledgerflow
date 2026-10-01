from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Response, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.database import get_db, AsyncSessionLocal
from backend.app.models.usage import UsageEvent
from backend.app.models.customer import Customer
from backend.app.models.billing import Subscription, SubscriptionStatus
from backend.app.schemas.usage import MeterEventCreate, MeterEventResponse
from backend.app.core.idempotency import (
    IdempotencyManager, IdempotencyConflictError, IdempotencyPayloadMismatchError
)
from backend.app.core.ledger_engine import generate_id

router = APIRouter(prefix="/meter-events", tags=["Usage Metering"])

@router.post("", response_model=MeterEventResponse)
async def ingest_meter_event(
    payload: MeterEventCreate,
    response: Response,
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_db)
):
    """
    Ingest a metered usage event (e.g. LLM tokens, GPU seconds) with strict idempotency.
    If the event_id is re-sent 50 times concurrently, only one record is written,
    and subsequent calls return the cached response with X-Idempotent-Replayed: true.
    """
    idempotency_key = idempotency_key_header or payload.event_id
    path = "/v1/meter-events"
    payload_dict = payload.model_dump(mode="json")

    try:
        is_replayed, cached_status, cached_body = await IdempotencyManager.check_or_create(
            key=idempotency_key,
            path=path,
            payload=payload_dict
        )
    except IdempotencyPayloadMismatchError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IdempotencyConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if is_replayed and cached_body:
        response.headers["X-Idempotent-Replayed"] = "true"
        cached_body["is_replayed"] = True
        return cached_body

    # Process new event
    try:
        # Validate customer
        cust_stmt = select(Customer).where(Customer.id == payload.customer_id)
        cust = (await session.execute(cust_stmt)).scalar_one_or_none()
        if not cust:
            raise HTTPException(status_code=404, detail=f"Customer {payload.customer_id} not found.")

        # Resolve active subscription if not provided
        sub_id = payload.subscription_id
        if not sub_id:
            sub_stmt = (
                select(Subscription)
                .where(Subscription.customer_id == payload.customer_id)
                .where(Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]))
                .order_by(Subscription.created_at.desc())
            )
            sub = (await session.execute(sub_stmt)).scalars().first()
            if sub:
                sub_id = sub.id

        event_id = generate_id("evt")
        event = UsageEvent(
            id=event_id,
            customer_id=payload.customer_id,
            subscription_id=sub_id,
            metric_name=payload.metric_name,
            quantity=payload.quantity,
            timestamp=payload.timestamp,
            idempotency_key=idempotency_key,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        resp_data = {
            "id": event.id,
            "customer_id": event.customer_id,
            "subscription_id": event.subscription_id,
            "metric_name": event.metric_name,
            "quantity": event.quantity,
            "timestamp": event.timestamp.isoformat(),
            "idempotency_key": event.idempotency_key,
            "is_replayed": False,
            "invoice_id": event.invoice_id,
            "created_at": event.created_at.isoformat(),
        }

        # Cache success in idempotency records
        await IdempotencyManager.record_success(
            key=idempotency_key,
            status_code=201,
            response_body=resp_data
        )

        response.status_code = 201
        return resp_data

    except HTTPException:
        await IdempotencyManager.record_failure(idempotency_key)
        raise
    except Exception as e:
        await IdempotencyManager.record_failure(idempotency_key)
        raise HTTPException(status_code=500, detail=f"Failed to record usage event: {str(e)}")

@router.get("", response_model=List[MeterEventResponse])
async def list_meter_events(
    customer_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_db)
):
    """List recent usage meter events."""
    query = select(UsageEvent).order_by(UsageEvent.timestamp.desc()).limit(limit)
    if customer_id:
        query = query.where(UsageEvent.customer_id == customer_id)
    events = (await session.execute(query)).scalars().all()
    return events
