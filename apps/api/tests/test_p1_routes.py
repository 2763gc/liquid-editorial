import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_til_public_and_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Public listing
        res = await client.get("/api/v1/til")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert len(data["items"]) >= 1

        # Tags
        tags_res = await client.get("/api/v1/til/tags")
        assert tags_res.status_code == 200
        tags = tags_res.json()
        assert len(tags) >= 1

        # Login admin to test creation
        login_res = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "admin123456"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create TIL
        create_res = await client.post(
            "/api/v1/admin/til",
            headers=headers,
            json={"title": "Test TIL", "tag": "test", "content_md": "Short TIL note"}
        )
        assert create_res.status_code == 201
        new_til = create_res.json()
        assert new_til["title"] == "Test TIL"

        # Update TIL
        update_res = await client.put(
            f"/api/v1/admin/til/{new_til['id']}",
            headers=headers,
            json={"title": "Updated Test TIL", "tag": "test", "content_md": "Updated note"}
        )
        assert update_res.status_code == 200

        # Delete TIL
        del_res = await client.delete(
            f"/api/v1/admin/til/{new_til['id']}",
            headers=headers
        )
        assert del_res.status_code == 200

@pytest.mark.asyncio
async def test_series_public():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/series")
        assert res.status_code == 200
        series_list = res.json()
        assert len(series_list) >= 1
        slug = series_list[0]["slug"]

        detail_res = await client.get(f"/api/v1/series/{slug}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["slug"] == slug
        assert "posts" in detail

@pytest.mark.asyncio
async def test_links_public_and_admin():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/links")
        assert res.status_code == 200
        links = res.json()
        assert len(links) >= 1
