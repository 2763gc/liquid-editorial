from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import ipaddress
import os

# 项目根目录：本地开发时是 <repo>/apps/api/app/core/config.py -> parents[4] = repo 根
# Docker 容器内是 /app/app/core/config.py，项目根为 /app（通过 parents[2] 或向上查找 .env）
_here = Path(__file__).resolve()
# 向上查找包含 .env 或 data 目录的项目根
BASE_DIR = _here.parents[2]  # 默认：/app (Docker) 或 <repo>/apps/api (本地)
for _p in _here.parents:
    if (_p / ".env").exists() or (_p / "docker-compose.yml").exists() or (_p / "data").is_dir():
        BASE_DIR = _p
        break
env_file = BASE_DIR / ".env"
default_db_dir = BASE_DIR / "data"
default_db_path = default_db_dir / "blog.db"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(env_file) if env_file.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    SITE_URL: str = "http://localhost:3000"
    SITE_TIMEZONE: str = "Asia/Shanghai"
    API_INTERNAL_URL: str = "http://127.0.0.1:8000"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{default_db_path.as_posix()}"
    JWT_SECRET: str = "super-secret-jwt-key-min-32-characters-for-liquid-editorial"
    HASH_SALT_SECRET: str = "visitor-salt-key-dev"
    REVALIDATE_SECRET: str = "internal-revalidate-secret-token"

    # 腾讯云 COS
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_BUCKET: str = ""
    COS_CDN_DOMAIN: str = ""
    COS_STS_DURATION: int = 900

    # GitHub
    GITHUB_TOKEN: str = ""

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    NOTIFY_EMAIL: str = ""

    # 后台安全
    ACCESS_TOKEN_MINUTES: int = 15
    SESSION_IDLE_DAYS: int = 7          # 刷新令牌的滑动有效期：7 天不用就作废
    SESSION_ABSOLUTE_DAYS: int = 30     # 一次登录最长 30 天，到期必须重新输入密码
    MAX_SESSIONS_PER_USER: int = 10
    # 只有来自这些地址的请求，才信任它带来的 X-Forwarded-For（本机的 Nitro / Nginx）
    TRUSTED_PROXIES: str = "127.0.0.1,::1"
    # Refresh Cookie 的 Secure 标记：留空时生产环境自动开启
    COOKIE_SECURE: bool | None = None

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.COOKIE_SECURE is None else self.COOKIE_SECURE

    def is_trusted_proxy(self, ip: str) -> bool:
        """TRUSTED_PROXIES 支持单个地址与网段，如 127.0.0.1,::1,172.16.0.0/12（Docker 内网）"""
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        return any(addr in net for net in _networks(self.TRUSTED_PROXIES))

    def production_problems(self) -> list[str]:
        """生产环境的配置自检：任何一条不满足都拒绝启动"""
        problems: list[str] = []
        for name in ("JWT_SECRET", "HASH_SALT_SECRET", "REVALIDATE_SECRET"):
            value = getattr(self, name)
            if value in _DEV_DEFAULTS or "replace-in-production" in value or len(value) < 32:
                problems.append(f"{name} 仍是开发默认值或短于 32 个字符")
        if len({self.JWT_SECRET, self.HASH_SALT_SECRET, self.REVALIDATE_SECRET}) < 3:
            problems.append("JWT_SECRET / HASH_SALT_SECRET / REVALIDATE_SECRET 不能相同")
        if not self.SITE_URL.startswith("https://"):
            problems.append("SITE_URL 必须是 https 地址")
        return problems


@lru_cache(maxsize=8)
def _networks(spec: str) -> tuple:
    nets = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            pass
    return tuple(nets)


_DEV_DEFAULTS = {
    "super-secret-jwt-key-min-32-characters-for-liquid-editorial",
    "visitor-salt-key-dev",
    "internal-revalidate-secret-token",
    # .env.example 里的占位值
    "super-secret-jwt-key-replace-in-production-min-32-chars",
    "visitor-salt-key-replace-in-production",
}

settings = Settings()
