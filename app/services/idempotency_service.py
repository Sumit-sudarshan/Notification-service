import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError
from app.models.idempotency_key import IdempotencyKey


def generate_request_hash(body: dict) -> str:
    """Creates a SHA-256 hash of the request body to detect payload changes."""
    body_str = json.dumps(body, sort_keys=True)
    return hashlib.sha256(body_str.encode("utf-8")).hexdigest()


async def check_idempotency(
    session: AsyncSession, user_id: str, key: str, request_hash: str
) -> tuple[bool, dict | None, int | None]:
    """
    Checks if an idempotency key exists and is valid.
    
    Returns a tuple of (is_found, response_body, response_status).
    Raises ConflictError if the key exists but the request hash is different.
    """
    stmt = select(IdempotencyKey).where(
        IdempotencyKey.user_id == user_id, 
        IdempotencyKey.key == key
    )
    result = await session.execute(stmt)
    idem_key = result.scalar_one_or_none()
    
    if not idem_key:
        return False, None, None
        
    # Check for payload mismatch
    if idem_key.request_hash != request_hash:
        raise ConflictError(
            "Idempotency key reused with a different payload. "
            "Please use a new Idempotency-Key for a different request."
        )
        
    # Valid replay
    return True, idem_key.response_body, idem_key.response_status


async def save_idempotency_key(
    session: AsyncSession, 
    user_id: str, 
    key: str, 
    request_hash: str, 
    response_status: int, 
    response_body: dict
) -> IdempotencyKey:
    """
    Saves the idempotency key and the associated response.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.IDEMPOTENCY_TTL_HOURS)
    
    idem_key = IdempotencyKey(
        user_id=user_id,
        key=key,
        request_hash=request_hash,
        response_status=response_status,
        response_body=response_body,
        expires_at=expires_at
    )
    session.add(idem_key)
    await session.commit()
    return idem_key
