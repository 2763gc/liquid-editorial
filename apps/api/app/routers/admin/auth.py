"""
后台登录、会话与安全设置

登录：密码 →（启用了两步验证时）验证码 → 建立会话。
限流按 15 分钟滑动窗口，记录在 login_attempts 表里（重启不丢）：
  同一账号 + 同一 IP 失败 5 次、同一账号失败 15 次、同一 IP 失败 30 次，任一触发即暂停。
  计数按用户名而不是按用户记，不存在的用户名表现完全一样，不泄露账号是否存在。
"""
import hmac
import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    ROTATION_GRACE_SECONDS,
    AuthContext,
    bearer_scheme,
    burn_password_check,
    create_access_token,
    create_mfa_token,
    decode_token,
    get_auth_context,
    hash_password,
    hash_recovery_codes,
    iso,
    keyed_hash,
    new_recovery_codes,
    new_refresh_secret,
    normalize_recovery_code,
    parse_iso,
    password_needs_rehash,
    password_problems,
    split_refresh_cookie,
    totp_match,
    totp_new_secret,
    totp_uri,
    utcnow,
    verify_password,
)
from app.core.visitor import RateLimiter, client_ip, mask_ip
from app.db.session import get_db
from app.models.security import AdminSession, AuditLog, LoginAttempt, UserSecurity
from app.models.user import User
from app.services.audit import audit, user_agent

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

ATTEMPT_WINDOW = timedelta(minutes=15)
LIMIT_USER_IP = 5
LIMIT_USER = 15
LIMIT_IP = 30
MFA_TRIES_PER_TOKEN = 5

# 进程内的突发限流：在跑 argon2 之前先挡掉，避免被当成 CPU 消耗攻击
login_burst = RateLimiter(limit=12, window_seconds=60)
# 需要重新验证身份的操作（改密、两步验证、恢复码）
reauth_limiter = RateLimiter(limit=6, window_seconds=300)
_mfa_tries: dict[str, int] = {}


# ---------------------------------------------------------------- 请求体

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(min_length=1, max_length=2048)
    code: str = Field(min_length=6, max_length=32)


class PasswordRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class ReauthRequest(PasswordRequest):
    code: str | None = Field(default=None, max_length=32)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)
    code: str | None = Field(default=None, max_length=32)


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


# ---------------------------------------------------------------- 小工具

def require_admin_client(request: Request) -> None:
    """
    只靠 Cookie 鉴权的接口（刷新、退出）要求带上自定义请求头：
    跨站页面无法在不经 CORS 预检的情况下加这个头，等于多一道 CSRF 防线
    """
    if request.headers.get("x-requested-with") != "blog-admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请求来源不受信任")


def user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "avatar_url": user.avatar_url,
        "last_login_at": user.last_login_at,
        "mfa_enabled": bool(user.totp_secret),
    }


def describe_ua(ua: str | None) -> str:
    if not ua:
        return "未知设备"
    if "Edg/" in ua:
        browser = "Edge"
    elif "OPR/" in ua:
        browser = "Opera"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Chrome/" in ua:
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    elif any(k in ua.lower() for k in ("curl", "python", "httpx", "wget", "postman")):
        browser = "脚本"
    else:
        browser = "浏览器"
    if "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
    elif "Android" in ua:
        os_name = "Android"
    elif "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"
    else:
        os_name = ""
    return f"{browser} · {os_name}" if os_name else browser


def set_refresh_cookie(response: Response, sid: str, secret: str, session: AdminSession) -> None:
    expires = min(parse_iso(session.expires_at), parse_iso(session.absolute_expires_at))
    max_age = max(60, int((expires - utcnow()).total_seconds()))
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=f"{sid}.{secret}",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=max_age,
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, secure=settings.cookie_secure, httponly=True, samesite="strict")


def refresh_denied(detail: str) -> JSONResponse:
    """刷新失败时顺手把失效的 Cookie 清掉（抛 HTTPException 会丢掉 Set-Cookie）"""
    res = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": {"code": "HTTP_401", "message": detail, "details": {}}},
    )
    clear_refresh_cookie(res)
    return res


def revoke(session: AdminSession, reason: str) -> None:
    if not session.revoked_at:
        session.revoked_at = iso(utcnow())
        session.revoke_reason = reason


async def revoke_sessions(db: AsyncSession, user_id: int, reason: str, keep: str | None = None) -> int:
    cond = [AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None)]
    if keep:
        cond.append(AdminSession.id != keep)
    res = await db.execute(update(AdminSession).where(*cond).values(revoked_at=iso(utcnow()), revoke_reason=reason))
    return res.rowcount or 0


async def security_row(db: AsyncSession, user_id: int) -> UserSecurity:
    sec = await db.get(UserSecurity, user_id)
    if not sec:
        sec = UserSecurity(user_id=user_id)
        db.add(sec)
        await db.flush()
    return sec


def recovery_hashes(sec: UserSecurity) -> list[str]:
    try:
        return list(json.loads(sec.recovery_codes or "[]"))
    except ValueError:
        return []


def check_second_factor(user: User, sec: UserSecurity, code: str | None) -> tuple[bool, bool]:
    """校验验证码或恢复码；命中时就地更新防重放计数 / 消耗恢复码。返回 (通过, 用的是恢复码)"""
    if not code or not user.totp_secret:
        return False, False
    raw = code.strip()
    if raw.replace(" ", "").isdigit():
        counter = totp_match(user.totp_secret, raw, sec.totp_last_counter)
        if counter is None:
            return False, False
        sec.totp_last_counter = counter
        return True, False
    norm = normalize_recovery_code(raw)
    if not norm:
        return False, False
    wanted = keyed_hash(norm, "recovery")
    hashes = recovery_hashes(sec)
    for stored in hashes:
        if hmac.compare_digest(stored, wanted):
            hashes.remove(stored)
            sec.recovery_codes = json.dumps(hashes)
            return True, True
    return False, False


# ---------------------------------------------------------------- 限流

async def attempt_state(db: AsyncSession, key: str, ip_hash: str) -> dict:
    now = utcnow()
    since = iso(now - ATTEMPT_WINDOW)
    last_ok = (
        await db.execute(select(func.max(LoginAttempt.at)).where(LoginAttempt.username == key, LoginAttempt.success == 1))
    ).scalar_one_or_none()
    floor = max(since, last_ok) if last_ok else since

    async def count(*cond):
        row = (await db.execute(select(func.count(), func.min(LoginAttempt.at)).where(LoginAttempt.success == 0, *cond))).one()
        return row[0], row[1]

    user_ip = await count(LoginAttempt.username == key, LoginAttempt.ip_hash == ip_hash, LoginAttempt.at > floor)
    user_all = await count(LoginAttempt.username == key, LoginAttempt.at > floor)
    ip_all = await count(LoginAttempt.ip_hash == ip_hash, LoginAttempt.at > since)
    return {"user_ip": user_ip, "user": user_all, "ip": ip_all}


def _retry_minutes(oldest: str | None) -> int:
    if not oldest:
        return int(ATTEMPT_WINDOW.total_seconds() // 60)
    left = parse_iso(oldest) + ATTEMPT_WINDOW - utcnow()
    return max(1, int(left.total_seconds() // 60) + 1)


def enforce_limits(state: dict) -> None:
    checks = [
        ("ip", LIMIT_IP, "当前网络的登录尝试过于频繁，请 {m} 分钟后再试"),
        ("user", LIMIT_USER, "该账号失败次数过多，已暂时锁定，请 {m} 分钟后再试"),
        ("user_ip", LIMIT_USER_IP, "连续登录失败次数过多，请 {m} 分钟后再试"),
    ]
    for name, limit, message in checks:
        n, oldest = state[name]
        if n >= limit:
            minutes = _retry_minutes(oldest)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=message.format(m=minutes),
                headers={"Retry-After": str(minutes * 60)},
            )


async def record_failure(db: AsyncSession, request: Request, key: str, ip_hash: str, stage: str, user: User | None, state: dict) -> str:
    db.add(LoginAttempt(at=iso(utcnow()), username=key, ip_hash=ip_hash, success=0, stage=stage))
    await audit(
        db, request, "auth.login_failed", user=user, actor=key[:64], level="warn",
        detail={"stage": stage}, commit=False,
    )
    if user:
        user.failed_login_count = (user.failed_login_count or 0) + 1
    await db.commit()
    left = LIMIT_USER_IP - (state["user_ip"][0] + 1)
    base = "验证码不正确" if stage == "mfa" else "用户名或密码错误"
    return f"{base}，还可尝试 {left} 次" if 0 < left <= 2 else base


# ---------------------------------------------------------------- 登录

async def complete_login(db: AsyncSession, request: Request, response: Response, user: User, key: str, ip_hash: str, mfa: bool) -> dict:
    now = utcnow()
    sid = secrets.token_urlsafe(16)
    secret = new_refresh_secret()
    session = AdminSession(
        id=sid,
        user_id=user.id,
        current_hash=keyed_hash(secret, "refresh"),
        created_at=iso(now),
        last_used_at=iso(now),
        expires_at=iso(now + timedelta(days=settings.SESSION_IDLE_DAYS)),
        absolute_expires_at=iso(now + timedelta(days=settings.SESSION_ABSOLUTE_DAYS)),
        ip_masked=mask_ip(client_ip(request)),
        user_agent=user_agent(request),
        mfa=1 if mfa else 0,
    )
    db.add(session)
    db.add(LoginAttempt(at=iso(now), username=key, ip_hash=ip_hash, success=1, stage="mfa" if mfa else "password"))
    previous_login = user.last_login_at
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = iso(now)
    await db.flush()

    # 每个账号最多保留若干个会话，超出的按最近使用时间淘汰
    active = (
        await db.execute(
            select(AdminSession)
            .where(AdminSession.user_id == user.id, AdminSession.revoked_at.is_(None))
            .order_by(desc(AdminSession.last_used_at), desc(AdminSession.created_at))
        )
    ).scalars().all()
    for old in active[settings.MAX_SESSIONS_PER_USER:]:
        if old.id != sid:
            revoke(old, "limit")

    await audit(db, request, "auth.login", user=user, target=sid[:8], detail={"mfa": mfa}, commit=False)
    await db.commit()
    set_refresh_cookie(response, sid, secret, session)
    return {
        "access_token": create_access_token(user, sid),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_MINUTES * 60,
        "user": user_dict(user),
        "previous_login_at": previous_login,
    }


@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    login_burst.check(f"login:{ip}")
    ip_hash = keyed_hash(ip, "ip")
    username = req.username.strip()
    key = username.lower()

    state = await attempt_state(db, key, ip_hash)
    enforce_limits(state)

    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user:
        burn_password_check(req.password)
        raise HTTPException(status_code=400, detail=await record_failure(db, request, key, ip_hash, "password", None, state))
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail=await record_failure(db, request, key, ip_hash, "password", user, state))

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(req.password)

    if user.totp_secret:
        await db.commit()
        return {"mfa_required": True, "mfa_token": create_mfa_token(user), "mfa_expires_in": 300}

    return await complete_login(db, request, response, user, key, ip_hash, mfa=False)


@router.post("/login/mfa")
async def login_mfa(req: MfaLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    ip = client_ip(request)
    login_burst.check(f"login:{ip}")
    ip_hash = keyed_hash(ip, "ip")
    payload = decode_token(req.mfa_token, "mfa")
    jti = str(payload.get("jti", ""))
    if _mfa_tries.get(jti, 0) >= MFA_TRIES_PER_TOKEN:
        raise HTTPException(status_code=401, detail="验证次数已用完，请重新输入密码")

    user = await db.get(User, int(payload["sub"]))
    if not user or not user.totp_secret or user.token_version != payload.get("token_version"):
        raise HTTPException(status_code=401, detail="登录已失效，请重新输入密码")
    key = user.username.lower()
    state = await attempt_state(db, key, ip_hash)
    enforce_limits(state)

    sec = await security_row(db, user.id)
    ok, used_recovery = check_second_factor(user, sec, req.code)
    if not ok:
        if len(_mfa_tries) > 2000:
            _mfa_tries.clear()
        _mfa_tries[jti] = _mfa_tries.get(jti, 0) + 1
        raise HTTPException(status_code=400, detail=await record_failure(db, request, key, ip_hash, "mfa", user, state))

    _mfa_tries[jti] = MFA_TRIES_PER_TOKEN  # 一张临时凭证只能换一次会话
    if used_recovery:
        await audit(db, request, "auth.recovery_code_used", user=user, level="warn",
                    detail={"remaining": len(recovery_hashes(sec))}, commit=False)
    result = await complete_login(db, request, response, user, key, ip_hash, mfa=True)
    if used_recovery:
        result["recovery_codes_remaining"] = len(recovery_hashes(sec))
    return result


# ---------------------------------------------------------------- 刷新与退出

@router.post("/refresh", dependencies=[Depends(require_admin_client)])
async def refresh_access_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    parsed = split_refresh_cookie(request.cookies.get(REFRESH_COOKIE))
    if not parsed:
        return refresh_denied("无有效的刷新凭据")
    sid, secret = parsed
    session = await db.get(AdminSession, sid)
    if not session or session.revoked_at:
        return refresh_denied("登录已失效，请重新登录")

    now = utcnow()
    absolute = parse_iso(session.absolute_expires_at)
    if parse_iso(session.expires_at) <= now or absolute <= now:
        revoke(session, "expired")
        await db.commit()
        return refresh_denied("登录已过期，请重新登录")

    user = await db.get(User, session.user_id)
    if not user:
        return refresh_denied("登录已失效，请重新登录")

    presented = keyed_hash(secret, "refresh")
    payload = {"token_type": "bearer", "expires_in": settings.ACCESS_TOKEN_MINUTES * 60, "user": user_dict(user)}

    if hmac.compare_digest(presented, session.current_hash):
        fresh = new_refresh_secret()
        session.previous_hash = session.current_hash
        session.current_hash = keyed_hash(fresh, "refresh")
        session.rotated_at = iso(now)
        session.last_used_at = iso(now)
        session.expires_at = iso(min(now + timedelta(days=settings.SESSION_IDLE_DAYS), absolute))
        await db.commit()
        set_refresh_cookie(response, sid, fresh, session)
        return {"access_token": create_access_token(user, sid), **payload}

    rotated = parse_iso(session.rotated_at)
    if (
        session.previous_hash
        and hmac.compare_digest(presented, session.previous_hash)
        and rotated
        and (now - rotated).total_seconds() <= ROTATION_GRACE_SECONDS
    ):
        # 多个标签页几乎同时刷新：浏览器里已经是新 Cookie 了，只补发访问令牌
        session.last_used_at = iso(now)
        await db.commit()
        return {"access_token": create_access_token(user, sid), **payload}

    # 已轮换掉的令牌又出现了：要么被盗用，要么被篡改。宁可错杀，整个会话作废
    revoke(session, "reuse")
    await audit(db, request, "auth.refresh_reuse", user=user, level="danger", target=sid[:8], commit=False)
    await db.commit()
    return refresh_denied("检测到登录凭据被重复使用，已强制退出该会话，请重新登录")


@router.post("/logout", dependencies=[Depends(require_admin_client)])
async def logout(
    request: Request,
    response: Response,
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """退出当前会话：凭 Cookie 或访问令牌找到会话并吊销；访问令牌过期也能退出"""
    session: AdminSession | None = None
    parsed = split_refresh_cookie(request.cookies.get(REFRESH_COOKIE))
    if parsed:
        candidate = await db.get(AdminSession, parsed[0])
        presented = keyed_hash(parsed[1], "refresh")
        if candidate and (
            hmac.compare_digest(presented, candidate.current_hash)
            or (candidate.previous_hash and hmac.compare_digest(presented, candidate.previous_hash))
        ):
            session = candidate
    if session is None and auth:
        try:
            sid = decode_token(auth.credentials, "access").get("sid")
            session = await db.get(AdminSession, sid) if sid else None
        except HTTPException:
            session = None

    if session and not session.revoked_at:
        revoke(session, "logout")
        user = await db.get(User, session.user_id)
        await audit(db, request, "auth.logout", user=user, target=session.id[:8], commit=False)
        await db.commit()
    clear_refresh_cookie(response)
    return {"message": "已安全退出登录"}


@router.post("/logout-all")
async def logout_all(request: Request, response: Response, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    """所有设备一起退出：吊销全部会话，并让已签发的访问令牌全部作废"""
    n = await revoke_sessions(db, ctx.user.id, "logout_all")
    ctx.user.token_version += 1
    await audit(db, request, "auth.logout_all", user=ctx.user, level="warn", detail={"sessions": n}, commit=False)
    await db.commit()
    clear_refresh_cookie(response)
    return {"message": "已退出全部设备", "revoked": n}


@router.get("/me")
async def get_current_user_profile(ctx: AuthContext = Depends(get_auth_context)):
    return {**user_dict(ctx.user), "session_id": ctx.session.id[:8], "session_mfa": bool(ctx.session.mfa)}


# ---------------------------------------------------------------- 安全概览与会话

@router.get("/security")
async def security_overview(ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    user = ctx.user
    sec = await db.get(UserSecurity, user.id)
    now = utcnow()
    active = (
        await db.execute(
            select(func.count()).where(
                AdminSession.user_id == user.id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > iso(now),
                AdminSession.absolute_expires_at > iso(now),
            )
        )
    ).scalar_one()
    failed = (
        await db.execute(
            select(func.count()).where(
                LoginAttempt.username == user.username.lower(),
                LoginAttempt.success == 0,
                LoginAttempt.at > iso(now - timedelta(hours=24)),
            )
        )
    ).scalar_one()
    return {
        "mfa_enabled": bool(user.totp_secret),
        "mfa_enabled_at": sec.totp_enabled_at if sec else None,
        "mfa_setup_pending": bool(sec and sec.totp_pending_secret),
        "recovery_codes_remaining": len(recovery_hashes(sec)) if sec else 0,
        "password_changed_at": sec.password_changed_at if sec else None,
        "last_login_at": user.last_login_at,
        "sessions_active": active,
        "failed_attempts_24h": failed,
        "session_mfa": bool(ctx.session.mfa),
        "policy": {
            "access_token_minutes": settings.ACCESS_TOKEN_MINUTES,
            "session_idle_days": settings.SESSION_IDLE_DAYS,
            "session_absolute_days": settings.SESSION_ABSOLUTE_DAYS,
            "lockout": {"window_minutes": int(ATTEMPT_WINDOW.total_seconds() // 60), "per_ip": LIMIT_USER_IP, "per_account": LIMIT_USER},
        },
    }


@router.get("/sessions")
async def list_sessions(ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    now = iso(utcnow())
    rows = (
        await db.execute(
            select(AdminSession)
            .where(
                AdminSession.user_id == ctx.user.id,
                AdminSession.revoked_at.is_(None),
                AdminSession.expires_at > now,
                AdminSession.absolute_expires_at > now,
            )
            .order_by(desc(AdminSession.last_used_at))
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": s.id,
                "current": s.id == ctx.session.id,
                "device": describe_ua(s.user_agent),
                "user_agent": s.user_agent,
                "ip_masked": s.ip_masked,
                "created_at": s.created_at,
                "last_used_at": s.last_used_at,
                "expires_at": min(s.expires_at, s.absolute_expires_at),
                "mfa": bool(s.mfa),
            }
            for s in rows
        ]
    }


@router.delete("/sessions/{sid}")
async def revoke_session(
    sid: str,
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(AdminSession, sid)
    if not session or session.user_id != ctx.user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    revoke(session, "revoked")
    await audit(db, request, "auth.session_revoked", user=ctx.user, target=sid[:8], commit=False)
    await db.commit()
    if sid == ctx.session.id:
        clear_refresh_cookie(response)
    return {"message": "该会话已退出"}


@router.post("/sessions/revoke-others")
async def revoke_other_sessions(request: Request, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    n = await revoke_sessions(db, ctx.user.id, "revoked", keep=ctx.session.id)
    await audit(db, request, "auth.sessions_revoked", user=ctx.user, level="warn", detail={"sessions": n}, commit=False)
    await db.commit()
    return {"message": f"已退出其他 {n} 个会话", "revoked": n}


# ---------------------------------------------------------------- 敏感操作：先重新验证身份

async def reauthenticate(db: AsyncSession, request: Request, ctx: AuthContext, password: str, code: str | None) -> UserSecurity:
    user = ctx.user
    reauth_limiter.check(f"reauth:{user.id}")
    # 复核失败与登录失败共用同一套持久限流：拿到会话的人也不能靠这里无限猜密码
    key = user.username.lower()
    ip_hash = keyed_hash(client_ip(request), "ip")
    enforce_limits(await attempt_state(db, key, ip_hash))
    sec = await security_row(db, user.id)

    async def fail(factor: str, message: str):
        db.add(LoginAttempt(at=iso(utcnow()), username=key, ip_hash=ip_hash, success=0, stage="reauth"))
        await audit(db, request, "auth.reauth_failed", user=user, level="warn", detail={"factor": factor})
        raise HTTPException(status_code=400, detail=message)

    if not verify_password(password, user.password_hash):
        await fail("password", "当前密码不正确")
    if user.totp_secret:
        ok, used_recovery = check_second_factor(user, sec, code)
        if not ok:
            await fail("totp", "两步验证码不正确" if code else "请输入两步验证码")
        if used_recovery:
            await audit(db, request, "auth.recovery_code_used", user=user, level="warn",
                        detail={"remaining": len(recovery_hashes(sec))}, commit=False)
    return sec


@router.post("/password")
async def change_password(
    req: PasswordChangeRequest,
    request: Request,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    user = ctx.user
    problems = password_problems(req.new_password, user.username)
    if problems:
        raise HTTPException(status_code=400, detail="新密码不符合要求：" + "；".join(problems))
    sec = await reauthenticate(db, request, ctx, req.current_password, req.code)
    if verify_password(req.new_password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    user.password_hash = hash_password(req.new_password)
    sec.password_changed_at = iso(utcnow())
    n = await revoke_sessions(db, user.id, "password_changed", keep=ctx.session.id)
    await audit(db, request, "auth.password_changed", user=user, level="warn", detail={"sessions_revoked": n}, commit=False)
    await db.commit()
    return {"message": "密码已更新", "revoked": n}


@router.post("/totp/setup")
async def totp_setup(req: PasswordRequest, request: Request, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    """生成一枚待确认的密钥；输入一次正确的验证码后才真正启用"""
    if ctx.user.totp_secret:
        raise HTTPException(status_code=400, detail="两步验证已启用")
    sec = await reauthenticate(db, request, ctx, req.password, None)
    secret = totp_new_secret()
    sec.totp_pending_secret = secret
    await db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, ctx.user.username)}


@router.post("/totp/enable")
async def totp_enable(req: TotpEnableRequest, request: Request, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    user = ctx.user
    if user.totp_secret:
        raise HTTPException(status_code=400, detail="两步验证已启用")
    sec = await security_row(db, user.id)
    if not sec.totp_pending_secret:
        raise HTTPException(status_code=400, detail="请先生成密钥")
    reauth_limiter.check(f"reauth:{user.id}")
    counter = totp_match(sec.totp_pending_secret, req.code)
    if counter is None:
        raise HTTPException(status_code=400, detail="验证码不正确，请确认手机时间准确后重试")

    codes = new_recovery_codes()
    user.totp_secret = sec.totp_pending_secret
    sec.totp_pending_secret = None
    sec.totp_enabled_at = iso(utcnow())
    sec.totp_last_counter = counter
    sec.recovery_codes = hash_recovery_codes(codes)
    ctx.session.mfa = 1
    # 其他会话是在没有两步验证时建立的，统统重新登录
    n = await revoke_sessions(db, user.id, "mfa_enabled", keep=ctx.session.id)
    await audit(db, request, "auth.mfa_enabled", user=user, level="warn", detail={"sessions_revoked": n}, commit=False)
    await db.commit()
    return {"recovery_codes": codes, "revoked": n}


@router.post("/totp/disable")
async def totp_disable(req: ReauthRequest, request: Request, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    user = ctx.user
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="两步验证未启用")
    sec = await reauthenticate(db, request, ctx, req.password, req.code)
    user.totp_secret = None
    sec.totp_pending_secret = None
    sec.totp_enabled_at = None
    sec.totp_last_counter = None
    sec.recovery_codes = None
    await audit(db, request, "auth.mfa_disabled", user=user, level="danger", commit=False)
    await db.commit()
    return {"message": "两步验证已停用"}


@router.post("/recovery-codes")
async def regenerate_recovery_codes(req: ReauthRequest, request: Request, ctx: AuthContext = Depends(get_auth_context), db: AsyncSession = Depends(get_db)):
    if not ctx.user.totp_secret:
        raise HTTPException(status_code=400, detail="请先启用两步验证")
    sec = await reauthenticate(db, request, ctx, req.password, req.code)
    codes = new_recovery_codes()
    sec.recovery_codes = hash_recovery_codes(codes)
    await audit(db, request, "auth.recovery_codes_regenerated", user=ctx.user, level="warn", commit=False)
    await db.commit()
    return {"recovery_codes": codes}


# ---------------------------------------------------------------- 审计日志

@router.get("/audit")
async def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    level: str | None = Query(None, pattern="^(info|warn|danger)$"),
    action: str | None = Query(None, max_length=64),
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    cond = []
    if level:
        cond.append(AuditLog.level == level)
    if action:
        cond.append(AuditLog.action.like(f"{action.replace('%', '')}%"))
    where = and_(*cond) if cond else true()
    total = (await db.execute(select(func.count()).select_from(AuditLog).where(where))).scalar_one()
    rows = (
        await db.execute(select(AuditLog).where(where).order_by(desc(AuditLog.id)).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    def detail(raw: str | None):
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    return {
        "items": [
            {
                "id": r.id,
                "at": r.at,
                "actor": r.actor,
                "action": r.action,
                "level": r.level,
                "target": r.target,
                "ip_masked": r.ip_masked,
                "device": describe_ua(r.user_agent) if r.user_agent else None,
                "detail": detail(r.detail),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
