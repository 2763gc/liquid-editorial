import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "storage" in data
        assert "disk" in data
        assert "uptime_seconds" in data

@pytest.mark.asyncio
async def test_site_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/site")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Luntrix's Editorial"
        assert "author" in data
        assert "appearance" in data
