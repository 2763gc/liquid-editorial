"""
后台鉴权

- 访问令牌：HS256 JWT，15 分钟，带会话号 sid。每次请求都核对会话仍然有效，吊销会话即刻生效
- 刷新令牌：不透明随机串「sid.secret」，只放在 HttpOnly + SameSite=Strict 的 Cookie 里，库里只存 HMAC。
  每次刷新都轮换；旧令牌在 30 秒宽限期外再次出现，判定为被盗用，整个会话吊销
- 两步验证：RFC 6238 TOTP（30 秒、6 位、SHA-1），同一时间片的验证码只能用一次；恢复码一次性
"""
import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.security import AdminSession
from app.models.user import User

ph = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)

ISSUER = "liquid-editorial"
REFRESH_COOKIE = "blog_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/admin/auth"
ROTATION_GRACE_SECONDS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


# ---------------------------------------------------------------- 密码

def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    try:
        return ph.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return True


_dummy_hash: str | None = None


def burn_password_check(plain_password: str) -> None:
    """用户名不存在时也跑一次同样耗时的校验，响应时间不泄露账号是否存在"""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = ph.hash(secrets.token_urlsafe(16))
    verify_password(plain_password, _dummy_hash)


COMMON_PASSWORDS = {
    "password", "passw0rd", "12345678", "123456789", "1234567890", "qwertyuiop", "11111111",
    "admin123", "admin123456", "administrator", "iloveyou", "letmein", "welcome", "abc12345",
    "qwerty123", "1q2w3e4r", "zaq12wsx", "88888888", "00000000", "woaini1314", "a123456789",
}


def password_problems(password: str, username: str = "") -> list[str]:
    """新密码的强度要求：至少 12 位；不足 16 位时需含三类字符；不含用户名；不在常见弱口令里"""
    problems: list[str] = []
    if len(password) < 12:
        problems.append("至少 12 个字符")
    if len(password) > 256:
        problems.append("不超过 256 个字符")
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if len(password) < 16 and classes < 3:
        problems.append("不足 16 位时需包含大写、小写、数字、符号中的三类")
    lowered = password.lower()
    if username and len(username) >= 3 and username.lower() in lowered:
        problems.append("不能包含用户名")
    if lowered in COMMON_PASSWORDS or len(set(password)) <= 3:
        problems.append("过于常见或重复")
    return problems


# ---------------------------------------------------------------- 令牌

def keyed_hash(value: str, purpose: str) -> str:
    """带用途的 HMAC-SHA256：刷新令牌、恢复码、IP 都用它入库，库文件泄露也还原不出原文"""
    key = hashlib.sha256(f"{purpose}|{settings.JWT_SECRET}".encode()).digest()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def create_access_token(user: User, sid: str) -> str:
    now = utcnow()
    payload = {
        "iss": ISSUER,
        "sub": str(user.id),
        "username": user.username,
        "sid": sid,
        "token_version": user.token_version,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_mfa_token(user: User) -> str:
    """密码已通过、等待第二步的临时凭证：5 分钟，只能用于提交验证码"""
    now = utcnow()
    payload = {
        "iss": ISSUER,
        "sub": str(user.id),
        "token_version": user.token_version,
        "type": "mfa",
        "jti": secrets.token_urlsafe(12),
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "type", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise unauthorized("登录凭证已过期")
    except jwt.PyJWTError:
        raise unauthorized("登录凭证无效")
    if payload.get("type") != expected_type:
        raise unauthorized("非法的令牌类型")
    return payload


def new_refresh_secret() -> str:
    return secrets.token_urlsafe(32)


def split_refresh_cookie(raw: str | None) -> tuple[str, str] | None:
    if not raw or raw.count(".") != 1:
        return None
    sid, secret = raw.split(".")
    if not sid or not secret or len(sid) > 64 or len(secret) > 128:
        return None
    return sid, secret


# ---------------------------------------------------------------- 当前登录

@dataclass
class AuthContext:
    user: User
    session: AdminSession


async def get_auth_context(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    if not auth:
        raise unauthorized("缺少访问凭证")
    payload = decode_token(auth.credentials, "access")
    sid = payload.get("sid")
    if not sid:
        raise unauthorized("登录凭证无效")

    row = (
        await db.execute(
            select(User, AdminSession)
            .join(AdminSession, AdminSession.user_id == User.id)
            .where(AdminSession.id == sid, User.id == int(payload["sub"]))
        )
    ).first()
    if not row:
        raise unauthorized("登录已失效，请重新登录")
    user, session = row
    if session.revoked_at:
        raise unauthorized("该会话已退出，请重新登录")
    if user.token_version != payload.get("token_version"):
        raise unauthorized("登录已失效，请重新登录")
    absolute = parse_iso(session.absolute_expires_at)
    if absolute and absolute <= utcnow():
        raise unauthorized("登录已过期，请重新登录")

    ctx = AuthContext(user=user, session=session)
    # 审计中间件从这里读操作人
    request.state.auth = ctx
    return ctx


async def get_current_user(ctx: AuthContext = Depends(get_auth_context)) -> User:
    return ctx.user


# ---------------------------------------------------------------- TOTP（RFC 6238）

TOTP_PERIOD = 30
TOTP_DIGITS = 6


def totp_new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _b32decode(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(secret: str, counter: int) -> str:
    digest = hmac.new(_b32decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** TOTP_DIGITS)
    return str(code).zfill(TOTP_DIGITS)


def totp_counter(at: float | None = None) -> int:
    return int((time.time() if at is None else at) // TOTP_PERIOD)


def totp_match(secret: str, code: str, last_counter: int | None = None, window: int = 1, at: float | None = None) -> int | None:
    """
    校验验证码，容忍前后各一个时间片的时钟误差。返回命中的时间片；
    不晚于上次已用的时间片一律拒绝（同一个码不能用两次）。
    """
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != TOTP_DIGITS:
        return None
    now = totp_counter(at)
    for counter in range(now - window, now + window + 1):
        if last_counter is not None and counter <= last_counter:
            continue
        if hmac.compare_digest(hotp(secret, counter), code):
            return counter
    return None


def totp_uri(secret: str, account: str, issuer: str = "Liquid Editorial") -> str:
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD}"


RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_recovery_codes(n: int = 10) -> list[str]:
    codes = []
    for _ in range(n):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    raw = "".join(ch for ch in code.lower() if ch.isalnum())
    return f"{raw[:5]}-{raw[5:]}" if len(raw) == 10 else ""


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([keyed_hash(c, "recovery") for c in codes])
