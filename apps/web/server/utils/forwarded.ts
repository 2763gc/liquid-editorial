import type { H3Event } from 'h3';

/**
 * 转发给 API 的 X-Forwarded-For。
 * 直连 Nitro 的一方是受信代理（本机、或 TRUSTED_PROXIES 里的 Nginx / Docker 内网）时，
 * 保留它带来的链路再追加它自己；否则客户端带来的 XFF 不可信，只写直连地址。
 * API 那边从右往左跳过受信代理，取第一个不受信的地址作为真实 IP。
 * TRUSTED_PROXIES 与 API 同一格式：逗号分隔的地址或 IPv4 网段，如 127.0.0.1,::1,172.16.0.0/12
 */
const SPEC = process.env.TRUSTED_PROXIES || '127.0.0.1,::1';

function plain(ip: string) {
  const v = ip.trim();
  return v.toLowerCase().startsWith('::ffff:') && v.includes('.') ? v.slice(7) : v;
}

function ipv4ToInt(ip: string): number | null {
  const parts = ip.split('.');
  if (parts.length !== 4) return null;
  let n = 0;
  for (const p of parts) {
    const v = Number(p);
    if (!/^\d{1,3}$/.test(p) || v > 255) return null;
    n = n * 256 + v;
  }
  return n;
}

const rules = SPEC.split(',').map((s) => s.trim()).filter(Boolean).map((rule) => {
  const [addr, bits] = rule.split('/');
  const base = ipv4ToInt(addr);
  if (base !== null && bits !== undefined) {
    const size = 2 ** (32 - Math.min(32, Math.max(0, Number(bits))));
    const start = Math.floor(base / size) * size;
    return (ip: string) => {
      const n = ipv4ToInt(ip);
      return n !== null && n >= start && n < start + size;
    };
  }
  return (ip: string) => ip.toLowerCase() === addr.toLowerCase();
});

function trusted(ip: string) {
  return rules.some((match) => match(ip));
}

export function forwardedFor(event: H3Event): string {
  const peer = plain(event.node.req.socket?.remoteAddress || '');
  const incoming = getRequestHeader(event, 'x-forwarded-for');
  // 没有对端地址：请求经由本机的 Unix 套接字 / 命名管道进来（nuxi dev 的工作进程、或 Nginx 走套接字），属于本机一跳
  if (!peer) return incoming || '127.0.0.1';
  if (trusted(peer) && incoming) return `${incoming}, ${peer}`;
  return peer;
}
