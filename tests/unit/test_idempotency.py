import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import ConflictError
from app.services.idempotency_service import check_idempotency, generate_request_hash

def test_generate_request_hash():
    body1 = {"b": 2, "a": 1}
    body2 = {"a": 1, "b": 2}
    # JSON sorting ensures these hash to the same value
    assert generate_request_hash(body1) == generate_request_hash(body2)
    
    body3 = {"a": 1, "b": 3}
    assert generate_request_hash(body1) != generate_request_hash(body3)

@pytest.mark.asyncio
async def test_check_idempotency_not_found():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    
    is_found, body, status = await check_idempotency(session, "user1", "key1", "hash1")
    assert is_found is False
    assert body is None
    assert status is None

@pytest.mark.asyncio
async def test_check_idempotency_conflict():
    session = AsyncMock()
    mock_key = MagicMock()
    mock_key.request_hash = "old_hash"
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_key
    session.execute.return_value = mock_result
    
    with pytest.raises(ConflictError, match="reused with a different payload"):
        await check_idempotency(session, "user1", "key1", "new_hash")

@pytest.mark.asyncio
async def test_check_idempotency_success():
    session = AsyncMock()
    mock_key = MagicMock()
    mock_key.request_hash = "hash1"
    mock_key.response_body = {"id": "123"}
    mock_key.response_status = 201
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_key
    session.execute.return_value = mock_result
    
    is_found, body, status = await check_idempotency(session, "user1", "key1", "hash1")
    assert is_found is True
    assert body == {"id": "123"}
    assert status == 201
