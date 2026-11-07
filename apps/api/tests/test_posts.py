import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_list_posts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/posts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 12
        assert len(data["items"]) >= 12
        first_post = data["items"][0]
        assert "title" in first_post
        assert "slug" in first_post
        assert "tags" in first_post

@pytest.mark.asyncio
async def test_get_post_detail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_res = await client.get("/api/v1/posts")
        slug = list_res.json()["items"][0]["slug"]

        response = await client.get(f"/api/v1/posts/{slug}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["slug"] == slug
        assert "content_md" in detail
        assert isinstance(detail["toc"], list)
        assert len(detail["tags"]) > 0

@pytest.mark.asyncio
async def test_view_post():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_res = await client.get("/api/v1/posts")
        slug = list_res.json()["items"][0]["slug"]
        orig_views = list_res.json()["items"][0]["view_count"]

        view_res = await client.post(f"/api/v1/posts/{slug}/view")
        assert view_res.status_code == 200
        assert view_res.json()["view_count"] == orig_views + 1

@pytest.mark.asyncio
async def test_list_tags():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tags")
        assert response.status_code == 200
        tags = response.json()
        assert len(tags) > 0
        assert any(t["name"] == "Rust" for t in tags)
