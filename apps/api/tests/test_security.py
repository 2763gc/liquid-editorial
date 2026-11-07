"""后台安全：会话与刷新令牌轮换、限流、两步验证、改密、上传校验、安全响应头、配置自检"""
import io
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from starlette.requests import Request

from app.core import security
from app.core.config import Settings
from app.core.security import hash_password, hotp, totp_counter, totp_match
from app.core.visitor import client_ip, mask_ip
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.routers.admin import auth as auth_router

PASSWORD = "Ink-and-Paper-2026!"
ADMIN_HEADERS = {"X-Requested-With": "blog-admin"}


async def make_user() -> str:
    username = f"sec-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as db:
        db.add(User(username=username, password_hash=hash_password(PASSWORD), display_name="安全测试", email=f"{username}@example.test"))
        await db.commit()
    return username


def client(ip: str) -> AsyncClient:
    # ASGI 测试客户端的直连地址是 127.0.0.1（受信代理），用 X-Forwarded-For 模拟不同来源，互不影响限流计数
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers={"x-forwarded-for": ip, "user-agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/130.0"})


def fresh_ip() -> str:
    n = uuid.uuid4().int
    return f"198.51.{n % 250}.{(n >> 8) % 250 + 1}"


async def login(c: AsyncClient, username: str, password: str = PASSWORD) -> dict:
    res = await c.post("/api/v1/admin/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def png_bytes(color: str = "#387E98") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color=color).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- 纯函数

def test_totp_rfc6238_vector():
    # RFC 6238 附录 B：ASCII "12345678901234567890"，T=59s → 8 位 94287082，取后 6 位
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert hotp(secret, 1) == "287082"
    assert totp_match(secret, "287082", at=59) == 1
    assert totp_match(secret, "287082", last_counter=1, at=59) is None  # 同一时间片不能重放
    assert totp_match(secret, "000000", at=59) is None


def test_client_ip_only_trusts_proxies(monkeypatch):
    def req(peer: str, xff: str | None = None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "client": (peer, 1234), "headers": headers})

    assert client_ip(req("203.0.113.9", "1.1.1.1")) == "203.0.113.9"  # 不受信的直连方，XFF 一律不看
    assert client_ip(req("127.0.0.1", "6.6.6.6, 198.51.100.7")) == "198.51.100.7"  # 取最右一个不受信地址
    assert client_ip(req("127.0.0.1", "198.51.100.7, 127.0.0.1")) == "198.51.100.7"
    assert mask_ip("198.51.100.7") == "198.51.100.*"
    # Docker 部署：Nginx 在内网网段里，配置成网段后同样能取到真实 IP
    assert client_ip(req("172.18.0.5", "198.51.100.7")) == "172.18.0.5"
    monkeypatch.setattr(security.settings, "TRUSTED_PROXIES", "127.0.0.1,::1,172.16.0.0/12")
    assert client_ip(req("172.18.0.5", "6.6.6.6, 198.51.100.7, 172.18.0.9")) == "198.51.100.7"
    assert client_ip(req("::ffff:172.18.0.5", "198.51.100.7")) == "198.51.100.7"
    assert mask_ip("::1") == "本机"
    assert mask_ip("2001:db8::1") == "2001:0db8:0000:…"


def test_production_config_validation():
    weak = Settings(APP_ENV="production", SITE_URL="http://example.com")
    weak.JWT_SECRET = "super-secret-jwt-key-min-32-characters-for-liquid-editorial"
    problems = weak.production_problems()
    assert any("JWT_SECRET" in p for p in problems)
    assert any("https" in p for p in problems)
    strong = Settings(
        APP_ENV="production",
        SITE_URL="https://example.com",
        JWT_SECRET="a" * 40,
        HASH_SALT_SECRET="b" * 40,
        REVALIDATE_SECRET="c" * 40,
    )
    assert strong.production_problems() == []
    placeholder = Settings(APP_ENV="production", SITE_URL="https://example.com", JWT_SECRET="super-secret-jwt-key-replace-in-production-min-32-chars",
                           HASH_SALT_SECRET="b" * 40, REVALIDATE_SECRET="c" * 40)
    assert any("JWT_SECRET" in p for p in placeholder.production_problems())
    assert strong.cookie_secure is True


def test_password_policy():
    assert security.password_problems("short")
    assert security.password_problems("admin123456")
    assert security.password_problems("alllowercaseletters12", "") == []  # 16 位以上不强制字符种类
    assert security.password_problems("Sec-tester-pass1", "sec-tester")  # 含用户名
    assert security.password_problems(PASSWORD) == []


# ---------------------------------------------------------------- 会话与刷新

@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_detection(monkeypatch):
    username = await make_user()
    async with client(fresh_ip()) as c:
        first = await login(c, username)
        old_cookie = c.cookies.get("blog_refresh_token")
        assert old_cookie and "." in old_cookie

        # 没有自定义请求头的刷新一律拒绝（CSRF 防线）
        assert (await c.post("/api/v1/admin/auth/refresh")).status_code == 403

        r1 = await c.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)
        assert r1.status_code == 200
        new_cookie = c.cookies.get("blog_refresh_token")
        assert new_cookie != old_cookie
        assert (await c.get("/api/v1/admin/auth/me", headers=bearer(r1.json()["access_token"]))).status_code == 200

        # 宽限期内旧令牌（多标签页并发刷新）：只补发访问令牌，不再轮换
        c.cookies.set("blog_refresh_token", old_cookie, path="/api/v1/admin/auth")
        r2 = await c.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)
        assert r2.status_code == 200
        assert "set-cookie" not in r2.headers

        # 宽限期外旧令牌再出现：判定被盗用，整个会话作废，连新令牌也不能用了
        monkeypatch.setattr(auth_router, "ROTATION_GRACE_SECONDS", -1)
        r3 = await c.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)
        assert r3.status_code == 401
        c.cookies.set("blog_refresh_token", new_cookie, path="/api/v1/admin/auth")
        assert (await c.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)).status_code == 401
        assert (await c.get("/api/v1/admin/auth/me", headers=bearer(first["access_token"]))).status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_session_and_sessions_api():
    username = await make_user()
    async with client(fresh_ip()) as a, client(fresh_ip()) as b:
        sa = await login(a, username)
        sb = await login(b, username)

        listed = await a.get("/api/v1/admin/auth/sessions", headers=bearer(sa["access_token"]))
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 2
        assert sum(1 for s in items if s["current"]) == 1
        assert all(s["ip_masked"].endswith(".*") for s in items)
        other = next(s for s in items if not s["current"])

        # 在 A 上踢掉 B
        assert (await a.delete(f"/api/v1/admin/auth/sessions/{other['id']}", headers=bearer(sa["access_token"]))).status_code == 200
        assert (await b.get("/api/v1/admin/auth/me", headers=bearer(sb["access_token"]))).status_code == 401
        assert (await b.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)).status_code == 401

        # A 退出：访问令牌即刻失效，刷新令牌也失效
        out = await a.post("/api/v1/admin/auth/logout", headers={**ADMIN_HEADERS, **bearer(sa["access_token"])})
        assert out.status_code == 200
        assert (await a.get("/api/v1/admin/auth/me", headers=bearer(sa["access_token"]))).status_code == 401


@pytest.mark.asyncio
async def test_logout_all_invalidates_every_token():
    username = await make_user()
    async with client(fresh_ip()) as a, client(fresh_ip()) as b:
        sa = await login(a, username)
        sb = await login(b, username)
        res = await a.post("/api/v1/admin/auth/logout-all", headers=bearer(sa["access_token"]))
        assert res.status_code == 200 and res.json()["revoked"] == 2
        for c, s in ((a, sa), (b, sb)):
            assert (await c.get("/api/v1/admin/auth/me", headers=bearer(s["access_token"]))).status_code == 401


# ---------------------------------------------------------------- 限流

@pytest.mark.asyncio
async def test_login_lockout_same_for_unknown_users():
    username = await make_user()
    ghost = f"ghost-{uuid.uuid4().hex[:6]}"
    async with client(fresh_ip()) as c:
        for name in (username, ghost):
            messages = []
            for _ in range(5):
                r = await c.post("/api/v1/admin/auth/login", json={"username": name, "password": "wrong-password"})
                assert r.status_code == 400
                messages.append(r.json()["error"]["message"])
            assert "还可尝试 1 次" in messages[3]
            blocked = await c.post("/api/v1/admin/auth/login", json={"username": name, "password": PASSWORD})
            assert blocked.status_code == 429  # 第 6 次即使密码正确也先被挡下
            assert int(blocked.headers["retry-after"]) > 0

    # 换一个网络，同一账号仍可登录（单 IP 的失败不会把账号彻底锁死）
    async with client(fresh_ip()) as c2:
        await login(c2, username)


# ---------------------------------------------------------------- 两步验证

@pytest.mark.asyncio
async def test_totp_enrollment_login_and_recovery():
    username = await make_user()
    async with client(fresh_ip()) as c:
        s = await login(c, username)
        h = bearer(s["access_token"])

        assert (await c.post("/api/v1/admin/auth/totp/setup", json={"password": "nope"}, headers=h)).status_code == 400
        setup = await c.post("/api/v1/admin/auth/totp/setup", json={"password": PASSWORD}, headers=h)
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")

        n = totp_counter()
        assert (await c.post("/api/v1/admin/auth/totp/enable", json={"code": "000000"}, headers=h)).status_code == 400
        enabled = await c.post("/api/v1/admin/auth/totp/enable", json={"code": hotp(secret, n)}, headers=h)
        assert enabled.status_code == 200
        codes = enabled.json()["recovery_codes"]
        assert len(codes) == 10

        overview = (await c.get("/api/v1/admin/auth/security", headers=h)).json()
        assert overview["mfa_enabled"] is True and overview["recovery_codes_remaining"] == 10

    async with client(fresh_ip()) as c:
        step1 = await c.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})
        assert step1.status_code == 200
        body = step1.json()
        assert body["mfa_required"] is True and "access_token" not in body
        assert c.cookies.get("blog_refresh_token") is None

        mfa = body["mfa_token"]
        # 临时凭证不能当访问令牌用
        assert (await c.get("/api/v1/admin/auth/me", headers=bearer(mfa))).status_code == 401
        assert (await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa, "code": "123456"})).status_code == 400
        # 启用时用过的验证码不能再用
        assert (await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa, "code": hotp(secret, n)})).status_code == 400
        ok = await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa, "code": hotp(secret, n + 1)})
        assert ok.status_code == 200, ok.text
        assert ok.json()["access_token"]
        # 一张临时凭证只能换一次
        assert (await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa, "code": codes[1]})).status_code == 401

    async with client(fresh_ip()) as c:
        mfa = (await c.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})).json()["mfa_token"]
        rec = await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa, "code": codes[0].upper().replace("-", " ")})
        assert rec.status_code == 200
        assert rec.json()["recovery_codes_remaining"] == 9
        h = bearer(rec.json()["access_token"])

        mfa2 = (await c.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})).json()["mfa_token"]
        assert (await c.post("/api/v1/admin/auth/login/mfa", json={"mfa_token": mfa2, "code": codes[0]})).status_code == 400

        # 停用需要密码 + 第二因素
        assert (await c.post("/api/v1/admin/auth/totp/disable", json={"password": PASSWORD}, headers=h)).status_code == 400
        off = await c.post("/api/v1/admin/auth/totp/disable", json={"password": PASSWORD, "code": codes[2]}, headers=h)
        assert off.status_code == 200

        audit = (await c.get("/api/v1/admin/auth/audit", headers=h, params={"action": "auth.mfa"})).json()["items"]
        actions = {a["action"] for a in audit if a["actor"] == username}
        assert {"auth.mfa_enabled", "auth.mfa_disabled"} <= actions


# ---------------------------------------------------------------- 改密

@pytest.mark.asyncio
async def test_password_change_revokes_other_sessions():
    username = await make_user()
    new_password = "Brush-Stroke-Rain-77"
    async with client(fresh_ip()) as a, client(fresh_ip()) as b:
        sa = await login(a, username)
        sb = await login(b, username)
        h = bearer(sa["access_token"])
        weak = await a.post("/api/v1/admin/auth/password", json={"current_password": PASSWORD, "new_password": "abc"}, headers=h)
        assert weak.status_code == 400 and "12" in weak.json()["error"]["message"]
        wrong = await a.post("/api/v1/admin/auth/password", json={"current_password": "nope", "new_password": new_password}, headers=h)
        assert wrong.status_code == 400
        ok = await a.post("/api/v1/admin/auth/password", json={"current_password": PASSWORD, "new_password": new_password}, headers=h)
        assert ok.status_code == 200 and ok.json()["revoked"] == 1
        assert (await a.get("/api/v1/admin/auth/me", headers=h)).status_code == 200  # 当前会话保留
        assert (await b.get("/api/v1/admin/auth/me", headers=bearer(sb["access_token"]))).status_code == 401

    async with client(fresh_ip()) as c:
        assert (await c.post("/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD})).status_code == 400
        await login(c, username, new_password)


# ---------------------------------------------------------------- 上传

@pytest.mark.asyncio
async def test_upload_hardening():
    username = await make_user()
    async with client(fresh_ip()) as c:
        h = bearer((await login(c, username))["access_token"])

        svg = await c.post("/api/v1/admin/media/sts", headers=h, json={"filename": "x.svg", "size_bytes": 100, "mime_type": "image/svg+xml"})
        assert svg.status_code == 415
        big = await c.post("/api/v1/admin/media/sts", headers=h, json={"filename": "x.png", "size_bytes": 40 * 1024 * 1024, "mime_type": "image/png"})
        assert big.status_code == 413

        # 路径穿越：对象键必须是服务端签发的格式
        evil = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": "../../apps/api/app/main.py"}, files={"file": ("a.png", png_bytes(), "image/png")})
        assert evil.status_code == 400
        forged = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": "media/2026/10/0123456789ab.png"}, files={"file": ("a.png", png_bytes(), "image/png")})
        assert forged.status_code == 400  # 格式对，但不是签发给自己的

        key = (await c.post("/api/v1/admin/media/sts", headers=h, json={"filename": "a.png", "size_bytes": 2048, "mime_type": "image/png"})).json()["cos_key"]
        assert key.endswith(".png")
        disguised = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
        r = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": key}, files={"file": ("a.png", disguised, "image/png")})
        assert r.status_code == 415

        jpeg = io.BytesIO()
        Image.new("RGB", (8, 8)).save(jpeg, format="JPEG")
        r = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": key}, files={"file": ("a.png", jpeg.getvalue(), "image/png")})
        assert r.status_code == 415  # 内容是 JPEG，声明是 PNG

        up = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": key}, files={"file": ("a.png", png_bytes(), "image/png")})
        assert up.status_code == 200
        assert up.json()["mime_type"] == "image/png" and up.json()["width"] == 32
        again = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": key}, files={"file": ("a.png", png_bytes(), "image/png")})
        assert again.status_code == 409  # 不覆盖

        # 登记时以服务端识别结果为准，客户端传来的地址、尺寸、类型都被忽略
        reg = await c.post("/api/v1/admin/media", headers=h, json={
            "cos_key": key, "url": "javascript:alert(1)", "original_name": "../../secret/a.png",
            "mime_type": "text/html", "size_bytes": 1, "width": 9999, "height": 9999,
        })
        assert reg.status_code == 200, reg.text
        m = reg.json()
        assert m["url"] == f"/media-dev/{key}" and m["mime_type"] == "image/png" and m["width"] == 32
        assert m["original_name"] == "a.png"

        # 签发给别人的对象键不能用
        other = await make_user()
        async with client(fresh_ip()) as c2:
            h2 = bearer((await login(c2, other))["access_token"])
            k2 = (await c2.post("/api/v1/admin/media/sts", headers=h2, json={"filename": "b.png", "size_bytes": 2048, "mime_type": "image/png"})).json()["cos_key"]
        stolen = await c.post("/api/v1/admin/media/upload-dev", headers=h, data={"cos_key": k2}, files={"file": ("b.png", png_bytes(), "image/png")})
        assert stolen.status_code == 400

        unknown = await c.post("/api/v1/admin/media", headers=h, json={
            "cos_key": "media/2026/10/ffffffffffff.png", "url": "/media-dev/media/2026/10/ffffffffffff.png",
            "original_name": "a.png", "mime_type": "image/png", "size_bytes": 10,
        })
        assert unknown.status_code == 400


# ---------------------------------------------------------------- 响应头与审计

@pytest.mark.asyncio
async def test_security_headers_and_audit_trail():
    username = await make_user()
    async with client(fresh_ip()) as c:
        health = await c.get("/api/v1/health")
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in health.headers["content-security-policy"]

        s = await login(c, username)
        h = bearer(s["access_token"])
        me = await c.get("/api/v1/admin/auth/me", headers=h)
        assert me.headers["cache-control"] == "no-store"

        created = await c.post("/api/v1/admin/posts", headers=h, json={"title": f"审计 {username}", "content_md": "正文", "status": "draft"})
        assert created.status_code == 200
        post_id = created.json()["id"]
        assert (await c.delete(f"/api/v1/admin/posts/{post_id}", headers=h)).status_code == 200

        items = (await c.get("/api/v1/admin/auth/audit", headers=h, params={"page_size": 100})).json()["items"]
        mine = [(i["action"], i["target"]) for i in items if i["actor"] == username]
        assert ("post.create", None) in mine
        assert ("post.delete", f"post:{post_id}") in mine
        assert any(a == "auth.login" for a, _ in mine)
        assert all(i["ip_masked"] in (None, "本机") or "*" in i["ip_masked"] or "…" in i["ip_masked"] for i in items)


@pytest.mark.asyncio
async def test_reauth_failures_share_login_limits():
    """拿到了会话的人，也不能在「复核身份」处无限猜密码"""
    username = await make_user()
    async with client(fresh_ip()) as c:
        h = bearer((await login(c, username))["access_token"])
        for _ in range(5):
            r = await c.post("/api/v1/admin/auth/totp/setup", json={"password": "guess-guess"}, headers=h)
            assert r.status_code == 400
        blocked = await c.post("/api/v1/admin/auth/totp/setup", json={"password": PASSWORD}, headers=h)
        assert blocked.status_code == 429
