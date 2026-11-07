import io
import pytest
from PIL import Image
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_admin_auth_and_crud():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 登录验证
        login_res = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "admin123456"}
        )
        assert login_res.status_code == 200
        tokens = login_res.json()
        assert "access_token" in tokens
        token = tokens["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. 获取当前用户信息
        me_res = await client.get("/api/v1/admin/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "admin"

        # 3. 创建文章草稿
        create_res = await client.post(
            "/api/v1/admin/posts",
            headers=headers,
            json={
                "title": "自动化测试特稿草稿",
                "subtitle": "通过 pytest 自动创建",
                "content_md": "## 章节一\n\n这里是自动化测试的内容。",
                "layout_variant": "standard",
                "status": "draft"
            }
        )
        assert create_res.status_code == 200
        post = create_res.json()
        post_id = post["id"]
        assert post["title"] == "自动化测试特稿草稿"
        assert post["status"] == "draft"

        # 4. 发布文章
        pub_res = await client.post(f"/api/v1/admin/posts/{post_id}/publish", headers=headers)
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"

        # 5. STS / 媒体上传与登记
        sts_res = await client.post(
            "/api/v1/admin/media/sts",
            headers=headers,
            json={"filename": "demo.png", "size_bytes": 1024, "mime_type": "image/png"}
        )
        assert sts_res.status_code == 200
        cos_key = sts_res.json()["cos_key"]

        # 生成真实有效测试图
        img = Image.new("RGB", (100, 80), color="#FF4D2E")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        upload_res = await client.post(
            "/api/v1/admin/media/upload-dev",
            headers=headers,
            data={"cos_key": cos_key},
            files={"file": ("demo.png", png_bytes, "image/png")}
        )
        assert upload_res.status_code == 200
        media_data = upload_res.json()
        assert media_data["width"] == 100
        assert media_data["height"] == 80
        assert media_data["dominant_color"] is not None

        reg_res = await client.post(
            "/api/v1/admin/media",
            headers=headers,
            json={
                "cos_key": cos_key,
                "url": media_data["url"],
                "original_name": "demo.png",
                "mime_type": "image/png",
                "size_bytes": len(png_bytes),
                "width": 100,
                "height": 80,
                "dominant_color": media_data["dominant_color"],
                "lqip": media_data.get("lqip")
            }
        )
        assert reg_res.status_code == 200

        # 6. 设置接口更新与读取
        set_res = await client.patch(
            "/api/v1/admin/settings",
            headers=headers,
            json={"site_title": "测试站名更新"}
        )
        assert set_res.status_code == 200

        get_set_res = await client.get("/api/v1/admin/settings", headers=headers)
        assert get_set_res.status_code == 200
        assert get_set_res.json()["site_title"] == "测试站名更新"

        # 7. 删除文章
        del_res = await client.delete(f"/api/v1/admin/posts/{post_id}", headers=headers)
        assert del_res.status_code == 200
