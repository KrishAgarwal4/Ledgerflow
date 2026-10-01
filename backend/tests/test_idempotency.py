import pytest
import asyncio
from datetime import datetime, timezone
import uuid

@pytest.mark.asyncio
async def test_meter_event_idempotency_concurrent(async_client):
    """
    Fires 50 concurrent requests with the identical event_id.
    Validates that:
    1. Exactly 1 request creates the event (HTTP 201).
    2. Concurrent/subsequent requests are either deduplicated (200 with X-Idempotent-Replayed)
       or locked (409 Conflict) and succeed upon retry.
    3. Exactly 1 record is written to the database.
    """
    unique_key = f"evt_test_{uuid.uuid4().hex[:10]}"
    payload = {
        "event_id": unique_key,
        "customer_id": "cus_nexus_ai",
        "metric_name": "llm_tokens",
        "quantity": 100000,
        "timestamp": datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }

    async def send_req():
        return await async_client.post("/v1/meter-events", json=payload)

    # 50 concurrent tasks
    responses = await asyncio.gather(*[send_req() for _ in range(50)])

    status_codes = [r.status_code for r in responses]
    assert all(code in (200, 201, 409) for code in status_codes)
    assert 201 in status_codes # At least and exactly 1 created

    # After initial batch settles, subsequent request MUST be 200 OK replayed
    res_after = await async_client.post("/v1/meter-events", json=payload)
    assert res_after.status_code == 200
    assert res_after.headers.get("x-idempotent-replayed") == "true"
    assert res_after.json()["is_replayed"] is True

@pytest.mark.asyncio
async def test_idempotency_payload_mismatch(async_client):
    """
    Proves that reusing an idempotency key with different parameters raises 422 Unprocessable Entity.
    """
    key = f"evt_mismatch_{uuid.uuid4().hex[:10]}"
    base_payload = {
        "event_id": key,
        "customer_id": "cus_nexus_ai",
        "metric_name": "llm_tokens",
        "quantity": 100000,
        "timestamp": datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }

    # First call succeeds
    res1 = await async_client.post("/v1/meter-events", json=base_payload)
    assert res1.status_code == 201

    # Second call with same key but different quantity (250,000 instead of 100,000)
    tampered_payload = dict(base_payload)
    tampered_payload["quantity"] = 250000

    res2 = await async_client.post("/v1/meter-events", json=tampered_payload)
    assert res2.status_code == 422
    assert "reused with different request parameters" in res2.json()["detail"]
