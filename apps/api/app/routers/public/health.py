import time
import shutil
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings, BASE_DIR

router = APIRouter(tags=["health"])

START_TIME = time.time()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    # 数据库可读写检查
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = (result.scalar() == 1)
    except Exception:
        db_ok = False

    # 生产环境只回答「活着没有」：磁盘、存储桶、运行环境不对外公开
    if settings.is_production:
        return {"status": "healthy" if db_ok else "unhealthy", "database": "connected" if db_ok else "disconnected", "version": "1.0.0"}

    # COS 状态评估
    cos_configured = bool(settings.COS_SECRET_ID and settings.COS_BUCKET)

    # 磁盘空间监控 (PRD 12.4)
    total, used, free = shutil.disk_usage(BASE_DIR)
    disk_info = {
        "total_gb": round(total / (1024 ** 3), 2),
        "used_gb": round(used / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
        "used_percent": round((used / total) * 100, 1)
    }

    uptime_sec = round(time.time() - START_TIME, 2)

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "uptime_seconds": uptime_sec,
        "database": "connected" if db_ok else "disconnected",
        "disk": disk_info,
        "storage": {
            "mode": "cos" if cos_configured else "local_fallback",
            "bucket": settings.COS_BUCKET if cos_configured else "local",
        },
        "environment": settings.APP_ENV,
        "version": "1.0.0",
    }
