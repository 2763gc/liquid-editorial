import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_projects_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/projects")
        assert res.status_code == 200
        projects = res.json()
        assert len(projects) >= 6
        assert projects[0]["name"] == "liquid-editorial"

        detail_res = await client.get("/api/v1/projects/liquid-editorial")
        assert detail_res.status_code == 200
        assert detail_res.json()["slug"] == "liquid-editorial"
        assert "stars" in detail_res.json()

@pytest.mark.asyncio
async def test_archive_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/archive")
        assert res.status_code == 200
        data = res.json()
        assert "stats" in data
        assert "years" in data
        assert data["stats"]["total_posts"] >= 12

@pytest.mark.asyncio
async def test_search_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/search?q=Rust")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        assert "results" in data
        assert any("Rust" in item["title"] for item in data["results"])

@pytest.mark.asyncio
async def test_comments_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_res = await client.get("/api/v1/posts")
        slug = list_res.json()["items"][0]["slug"]

        post_res = await client.post(
            f"/api/v1/posts/{slug}/comments",
            json={
                "author_name": "读者小明",
                "author_email": "xiaoming@example.com",
                "content_md": "这篇特稿写得非常深刻，受益匪浅！"
            }
        )
        assert post_res.status_code == 200
        c_data = post_res.json()
        assert c_data["author_name"] == "读者小明"

        get_res = await client.get(f"/api/v1/posts/{slug}/comments")
        assert get_res.status_code == 200
        assert get_res.json()["total"] >= 1

@pytest.mark.asyncio
async def test_feed_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/feed")
        assert res.status_code == 200
        items = res.json()
        assert len(items) > 0
        assert "title" in items[0]
        assert "content_md" in items[0]
