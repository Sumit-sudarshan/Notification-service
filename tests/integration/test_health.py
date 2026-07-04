import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "notification-service"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_unauthorized_request(client):
    """No X-API-Key → 401."""
    response = await client.post("/api/v1/notifications", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wrong_api_key(client):
    """Wrong X-API-Key → 401."""
    response = await client.post(
        "/api/v1/notifications",
        json={},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_notification_validation_error(auth_client):
    """Missing required fields → 422 from Pydantic."""
    response = await auth_client.post("/api/v1/notifications", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_notification_not_found(auth_client, mock_db, monkeypatch):
    """Unknown UUID → 404."""
    from app.db.session import get_db
    app_instance = auth_client._transport.app  # type: ignore[attr-defined]
    app_instance.dependency_overrides[get_db] = lambda: mock_db

    response = await auth_client.get(
        "/api/v1/notifications/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
    app_instance.dependency_overrides.clear()
