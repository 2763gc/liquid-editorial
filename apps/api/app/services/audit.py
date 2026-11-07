"""后台审计日志：登录、会话、安全设置由鉴权接口直接记；其余写操作由 main.py 的中间件统一记"""
import json
import logging
from typing import Any

from fastapi import Request
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import iso, utcnow
from app.core.visitor import client_ip, mask_ip
from app.models.security import AuditLog, LoginAttempt
from app.models.user import User

log = logging.getLogger("app.audit")

AUDIT_RETENTION_DAYS = 180
ATTEMPT_RETENTION_DAYS = 30


def user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent", "")
    return ua[:300] or None


def build_audit(
    request: Request | None,
    action: str,
    *,
    user: User | None = None,
    actor: str | None = None,
    level: str = "info",
    target: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog(
        at=iso(utcnow()),
        user_id=user.id if user else None,
        actor=actor or (user.username if user else None),
        action=action,
        level=level,
        target=target,
        ip_masked=mask_ip(client_ip(request)) if request is not None else None,
        user_agent=user_agent(request),
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
    )


async def audit(db: AsyncSession, request: Request | None, action: str, *, commit: bool = True, **kwargs) -> None:
    """记一条审计；失败只写日志，不影响业务"""
    try:
        entry = build_audit(request, action, **kwargs)
        db.add(entry)
        if commit:
            await db.commit()
            if entry.id and entry.id % 200 == 0:
                await prune(db)
    except Exception:  # pragma: no cover - 审计不能把正常请求搞挂
        log.exception("audit write failed: %s", action)


async def prune(db: AsyncSession) -> None:
    from datetime import timedelta

    now = utcnow()
    await db.execute(delete(AuditLog).where(AuditLog.at < iso(now - timedelta(days=AUDIT_RETENTION_DAYS))))
    await db.execute(delete(LoginAttempt).where(LoginAttempt.at < iso(now - timedelta(days=ATTEMPT_RETENTION_DAYS))))
    await db.commit()
