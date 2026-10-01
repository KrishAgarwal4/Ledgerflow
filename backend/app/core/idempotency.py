import hashlib
import json
from typing import Optional, Tuple, Any, Dict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.idempotency import IdempotencyRecord
from backend.app.database import AsyncSessionLocal

class IdempotencyConflictError(Exception):
    def __init__(self, message: str = "A request with this idempotency key is currently being processed."):
        super().__init__(message)

class IdempotencyPayloadMismatchError(Exception):
    def __init__(self, message: str = "Idempotency key reused with different request parameters."):
        super().__init__(message)

def compute_payload_hash(path: str, payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{path}:{serialized}".encode("utf-8")).hexdigest()

class IdempotencyManager:
    @staticmethod
    async def check_or_create(
        key: str,
        path: str,
        payload: Any
    ) -> Tuple[bool, Optional[int], Optional[Dict[str, Any]]]:
        """
        Returns:
            (is_replayed, cached_status_code, cached_response_body)
            If is_replayed is True, caller returns cached response with X-Idempotent-Replayed: true.
            If is_replayed is False, key was reserved as PROCESSING and caller executes business logic.
        """
        req_hash = compute_payload_hash(path, payload)

        async with AsyncSessionLocal() as session:
            try:
                query = select(IdempotencyRecord).where(IdempotencyRecord.key == key).with_for_update()
                record = (await session.execute(query)).scalar_one_or_none()

                if record is not None:
                    if record.request_hash != req_hash:
                        raise IdempotencyPayloadMismatchError()
                    
                    if record.status == "PROCESSING":
                        raise IdempotencyConflictError()
                    
                    if record.status == "SUCCEEDED":
                        return True, record.status_code, record.response_body

                    # Previously failed: allow retry
                    record.status = "PROCESSING"
                    record.request_hash = req_hash
                    await session.commit()
                    return False, None, None

                # New key: claim as PROCESSING
                new_record = IdempotencyRecord(
                    key=key,
                    path=path,
                    request_hash=req_hash,
                    status="PROCESSING"
                )
                session.add(new_record)
                await session.commit()
                return False, None, None

            except IntegrityError:
                await session.rollback()
                # Race condition: concurrent worker inserted the record at the same millisecond.
                # Re-read the record committed by the winning worker.
                query = select(IdempotencyRecord).where(IdempotencyRecord.key == key)
                rec = (await session.execute(query)).scalar_one_or_none()
                if rec:
                    if rec.request_hash != req_hash:
                        raise IdempotencyPayloadMismatchError()
                    if rec.status == "PROCESSING":
                        raise IdempotencyConflictError()
                    if rec.status == "SUCCEEDED":
                        return True, rec.status_code, rec.response_body
                raise IdempotencyConflictError()

    @staticmethod
    async def record_success(
        key: str,
        status_code: int,
        response_body: Dict[str, Any]
    ) -> None:
        async with AsyncSessionLocal() as session:
            query = select(IdempotencyRecord).where(IdempotencyRecord.key == key).with_for_update()
            record = (await session.execute(query)).scalar_one_or_none()
            if record:
                record.status = "SUCCEEDED"
                record.status_code = status_code
                record.response_body = response_body
                await session.commit()

    @staticmethod
    async def record_failure(key: str) -> None:
        async with AsyncSessionLocal() as session:
            query = select(IdempotencyRecord).where(IdempotencyRecord.key == key).with_for_update()
            record = (await session.execute(query)).scalar_one_or_none()
            if record:
                record.status = "FAILED"
                await session.commit()
