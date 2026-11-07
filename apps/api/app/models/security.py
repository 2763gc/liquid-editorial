"""后台安全相关的表：登录会话、登录尝试、审计日志、用户安全设置（两步验证与恢复码）"""
from sqlalchemy import Index, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminSession(Base):
    """
    一次登录 = 一个会话。刷新令牌是不透明的随机串，库里只存它的 SHA-256：
    - current_hash：当前有效的刷新令牌
    - previous_hash：上一个刷新令牌。轮换后若有人再拿旧令牌来换，判定为令牌被盗用，整个会话立即吊销
    访问令牌里带 sid，吊销会话后它签发过的访问令牌随即失效。
    """

    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    current_hash: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    rotated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    last_used_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    absolute_expires_at: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LoginAttempt(Base):
    """登录尝试（成功与失败都记），用于按 IP、按账号限流与锁定；只存 IP 的加盐哈希"""

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(Text, default="password", nullable=False)  # password / mfa

    __table_args__ = (
        Index("idx_login_attempts_ip_at", "ip_hash", "at"),
        Index("idx_login_attempts_user_at", "username", "at"),
    )


class AuditLog(Base):
    """后台审计日志：谁、何时、从哪儿、做了什么。不记录密码、令牌与完整 IP"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    level: Mapped[str] = mapped_column(Text, default="info", nullable=False)  # info / warn / danger
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_masked: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserSecurity(Base):
    """
    用户安全设置。users 表已有 totp_secret（启用后的密钥）；这里放启用过程中的待确认密钥、
    恢复码（只存哈希，一次性）、上次使用的 TOTP 时间片（防重放）与改密时间。
    """

    __tablename__ = "user_security"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    totp_pending_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_last_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_codes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON：哈希列表
    password_changed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
