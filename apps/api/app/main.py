import sys
from pathlib import Path
from contextlib import asynccontextmanager

# 确保 apps/api 目录始终在 sys.path 中，支持直接通过 python main.py 运行
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import time
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base
from app.models import *
from app.services.cos import DEV_MEDIA_DIR, MAX_UPLOAD_BYTES
from app.services.audit import build_audit
from app.routers.public import (
    health,
    site,
    posts as public_posts,
    tags as public_tags,
    projects as public_projects,
    archive as public_archive,
    search as public_search,
    comments as public_comments,
    feed as public_feed,
    til as public_til,
    series as public_series,
    links as public_links,
    stats as public_stats,
)
from app.routers.admin import (
    auth as admin_auth,
    posts as admin_posts,
    media as admin_media,
    settings as admin_settings,
    til as admin_til,
    links as admin_links,
)

# 生产环境配置自检：默认密钥、过短密钥、非 https 站点一律拒绝启动
if settings.is_production:
    _problems = settings.production_problems()
    if _problems:
        raise RuntimeError("生产环境配置不安全，拒绝启动：\n- " + "\n- ".join(_problems))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保数据库与表初始化
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭引擎连接
    await engine.dispose()

app = FastAPI(
    title="Liquid Editorial API",
    version="1.0.0",
    description="空间化个人技术博客 REST API",
    # 接口文档只在开发环境开放
    docs_url=None if settings.is_production else "/api/v1/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS：浏览器经 Nitro 同源代理访问，跨源只放行站点本身（开发时加上本机地址）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.SITE_URL] if settings.is_production else [settings.SITE_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# ---------------------------------------------------------------- 安全中间件
BODY_LIMIT_UPLOAD = MAX_UPLOAD_BYTES + 256 * 1024
BODY_LIMIT_ADMIN = 5 * 1024 * 1024
BODY_LIMIT_PUBLIC = 256 * 1024
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# 后台写操作 → 审计动作名；不在表里的（申请上传凭证、上传原文件）不记
AUDIT_ACTIONS = {
    "admin_create_post": "post.create",
    "admin_update_post": "post.update",
    "admin_publish_post": "post.publish",
    "admin_delete_post": "post.delete",
    "update_admin_settings": "settings.update",
    "create_til": "til.create",
    "update_til": "til.update",
    "delete_til": "til.delete",
    "create_link": "link.create",
    "update_link": "link.update",
    "delete_link": "link.delete",
    "register_media": "media.upload",
    "delete_media": "media.delete",
}
AUDIT_LEVELS = {"post.delete": "warn", "media.delete": "warn", "link.delete": "warn", "til.delete": "warn", "settings.update": "warn"}
# 连续保存同一篇稿子只记一次（5 分钟内）
_recent_updates: dict[tuple, float] = {}

def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "details": {}}})

async def _audit_write(request: Request, status_code: int) -> None:
    endpoint = request.scope.get("endpoint")
    action = AUDIT_ACTIONS.get(getattr(endpoint, "__name__", ""))
    ctx = getattr(request.state, "auth", None)
    if not action or ctx is None:
        return
    params = request.scope.get("path_params") or {}
    target = ",".join(f"{k.removesuffix('_id')}:{v}" for k, v in params.items()) or None
    if action.endswith(".update"):
        key = (ctx.user.id, action, target)
        now = time.monotonic()
        if now - _recent_updates.get(key, 0) < 300:
            return
        if len(_recent_updates) > 500:
            _recent_updates.clear()
        _recent_updates[key] = now
    try:
        async with AsyncSessionLocal() as db:
            db.add(build_audit(request, action, user=ctx.user, level=AUDIT_LEVELS.get(action, "info"), target=target, detail={"status": status_code}))
            await db.commit()
    except Exception:
        import logging

        logging.getLogger("app.audit").exception("audit middleware failed")

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path
    is_admin = path.startswith("/api/v1/admin/")

    # 请求体上限：按 Content-Length 先挡一道（生产环境 Nginx 还有 client_max_body_size）
    length = request.headers.get("content-length")
    if length and length.isdigit():
        if path.endswith("/admin/media/upload-dev"):
            limit = BODY_LIMIT_UPLOAD
        else:
            limit = BODY_LIMIT_ADMIN if is_admin else BODY_LIMIT_PUBLIC
        if int(length) > limit:
            return _error(413, "PAYLOAD_TOO_LARGE", "请求体过大")

    response = await call_next(request)

    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Cross-Origin-Resource-Policy", "same-site")
    if path.startswith("/media-dev/"):
        # 用户上传的文件：即便混进了可执行内容，也不让它在本站源下运行
        h["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
    elif not path.startswith("/api/v1/docs"):
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if is_admin:
        h["Cache-Control"] = "no-store"
        h["Pragma"] = "no-cache"
    if settings.is_production:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    if is_admin and request.method in WRITE_METHODS and response.status_code < 400 and not path.startswith("/api/v1/admin/auth/"):
        await _audit_write(request, response.status_code)
    return response

# 本地媒体静态托管服务 (开发降级模式)
DEV_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media-dev", StaticFiles(directory=str(DEV_MEDIA_DIR)), name="media-dev")

# 统一错误响应结构 (PRD 9.1)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "details": {},
            }
        },
        # Retry-After、WWW-Authenticate 等要一并带回
        headers=getattr(exc, "headers", None),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """未捕获的异常也走统一错误格式（B29）；细节只写日志，不回给客户端"""
    import logging

    logging.getLogger("app").exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "INTERNAL_ERROR", "message": "服务器开了个小差，请稍后再试", "details": {}}},
    )

# 注册公开路由 (PRD 9.2)
app.include_router(health.router, prefix="/api/v1")
app.include_router(site.router, prefix="/api/v1")
app.include_router(public_posts.router, prefix="/api/v1")
app.include_router(public_tags.router, prefix="/api/v1")
app.include_router(public_projects.router, prefix="/api/v1")
app.include_router(public_archive.router, prefix="/api/v1")
app.include_router(public_search.router, prefix="/api/v1")
app.include_router(public_comments.router, prefix="/api/v1")
app.include_router(public_feed.router, prefix="/api/v1")
app.include_router(public_til.router, prefix="/api/v1")
app.include_router(public_series.router, prefix="/api/v1")
app.include_router(public_links.router, prefix="/api/v1")
app.include_router(public_stats.router, prefix="/api/v1")

# 注册管理后台接口
app.include_router(admin_auth.router, prefix="/api/v1")
app.include_router(admin_posts.router, prefix="/api/v1")
app.include_router(admin_media.router, prefix="/api/v1")
app.include_router(admin_settings.router, prefix="/api/v1")
app.include_router(admin_til.router, prefix="/api/v1")
app.include_router(admin_links.router, prefix="/api/v1")

@app.get("/")
async def root():
    info = {"name": "Liquid Editorial API", "health": "/api/v1/health"}
    if not settings.is_production:
        info["docs"] = "/api/v1/docs"
    return info

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
