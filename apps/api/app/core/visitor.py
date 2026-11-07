"""访客识别与轻量限流（无 Cookie，按 PRD 8.8 的方式加盐哈希）"""
import hashlib
import ipaddress
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.core.config import settings


def _plain(ip: str) -> str:
    """IPv4 映射的 IPv6（::ffff:127.0.0.1）还原成 IPv4，受信代理名单才对得上"""
    ip = ip.strip()
    return ip[7:] if ip.lower().startswith("::ffff:") and "." in ip else ip


def client_ip(request: Request) -> str:
    """
    真实客户端 IP。只有直连方是受信代理（本机的 Nitro / Nginx）时才看 X-Forwarded-For，
    并从右往左跳过受信代理，取第一个不受信的地址——左边的部分客户端可以随便写，不能信。
    """
    peer = _plain(request.client.host if request.client else "")
    if peer and not settings.is_trusted_proxy(peer):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [_plain(h) for h in forwarded.split(",") if h.strip()]
    for hop in reversed(hops):
        if not settings.is_trusted_proxy(hop):
            return hop
    if hops:
        return hops[0]
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    return peer or "0.0.0.0"


def mask_ip(ip: str) -> str:
    """审计与会话列表里只显示 IP 的前半段：IPv4 保留前三段，IPv6 保留前三组；本机地址直接写「本机」"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "未知"
    if addr.is_loopback or addr.is_unspecified:
        return "本机"
    if addr.version == 4:
        return ".".join(ip.split(".")[:3]) + ".*"
    return ":".join(addr.exploded.split(":")[:3]) + ":…"


def visitor_hash(request: Request, daily: bool = False) -> str:
    """同一 IP + UA 得到同一哈希；daily=True 时盐按天轮换，无法跨天追踪"""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d") if daily else ""
    raw = f"{client_ip(request)}|{request.headers.get('user-agent', '')}|{day}|{settings.HASH_SALT_SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class RateLimiter:
    """进程内滑动窗口限流。单进程部署足够；多 worker 时每个 worker 各自计数。"""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        bucket = self.hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试")
        bucket.append(now)
        if len(self.hits) > 10000:
            for k in list(self.hits.keys())[:5000]:
                if not self.hits[k]:
                    del self.hits[k]
