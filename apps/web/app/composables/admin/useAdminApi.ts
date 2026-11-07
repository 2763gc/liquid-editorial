import { shallowRef } from 'vue';

/**
 * 后台接口调用
 * - 访问令牌只放在内存里：不进 localStorage，页面里就算混进了恶意脚本，也拿不走能长期使用的凭据
 * - 刷新令牌在 HttpOnly + SameSite=Strict 的 Cookie 里；页面刷新后用它静默换一枚新的访问令牌
 * - 快过期时先刷新再请求；401 时刷新一次再重试，仍失败就带上 redirect 回登录页
 * - 刷新令牌每用一次就轮换，所以同一标签页内的并发请求共享同一次刷新
 * - 多个标签页之间用 BroadcastChannel 同步「退出」与「有人在操作」（空闲自动退出用）
 */
export interface AdminUser {
  id: number;
  username: string;
  display_name?: string | null;
  email?: string | null;
  avatar_url?: string | null;
  last_login_at?: string | null;
  mfa_enabled?: boolean;
}

interface TokenPayload {
  access_token: string;
  expires_in?: number;
  user?: AdminUser;
}

const LEGACY_KEY = 'blog_access_token';
// 只是一个「这台浏览器登录过」的提示，不是凭据：没有它就不必发一次注定 401 的刷新请求
const HINT_KEY = 'blog_admin_hint';
const CLIENT_HEADER = { 'X-Requested-With': 'blog-admin' };

let accessToken: string | null = null;
let expiresAt = 0;
let refreshing: Promise<string | null> | null = null;

/** 当前登录的编辑（登录、刷新时更新） */
export const adminUser = shallowRef<AdminUser | null>(null);

type ChannelMessage = { type: 'logout'; reason?: string } | { type: 'activity'; at: number };
const channel: BroadcastChannel | null = import.meta.client && typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('blog-admin') : null;
const listeners = new Set<(msg: ChannelMessage) => void>();
channel?.addEventListener('message', (e: MessageEvent<ChannelMessage>) => {
  if (e.data?.type === 'logout') forget();
  listeners.forEach((fn) => fn(e.data));
});

/** 订阅其他标签页的消息，返回取消函数 */
export function onAdminChannel(fn: (msg: ChannelMessage) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
export function broadcastAdmin(msg: ChannelMessage) {
  channel?.postMessage(msg);
}

// 旧版本把访问令牌存在 localStorage，升级后顺手清掉
if (import.meta.client) {
  try { localStorage.removeItem(LEGACY_KEY); } catch {}
}

function hint(on?: boolean): boolean {
  try {
    if (on === true) localStorage.setItem(HINT_KEY, '1');
    else if (on === false) localStorage.removeItem(HINT_KEY);
    return localStorage.getItem(HINT_KEY) === '1';
  } catch {
    return true;
  }
}

function forget() {
  accessToken = null;
  expiresAt = 0;
  adminUser.value = null;
  if (import.meta.client) hint(false);
}

export function getAdminToken(): string | null {
  return accessToken;
}

/** 保存登录或刷新得到的访问令牌（只在内存里） */
export function acceptAdminSession(payload: TokenPayload | null) {
  if (!payload?.access_token) {
    forget();
    return;
  }
  accessToken = payload.access_token;
  expiresAt = Date.now() + (payload.expires_in ?? 900) * 1000;
  if (payload.user) adminUser.value = payload.user;
  hint(true);
}

function refreshToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = $fetch<TokenPayload>('/api/v1/admin/auth/refresh', { method: 'POST', headers: CLIENT_HEADER })
      .then((r) => {
        acceptAdminSession(r);
        return r.access_token;
      })
      .catch(() => {
        forget();
        return null;
      })
      .finally(() => {
        setTimeout(() => { refreshing = null; }, 0);
      });
  }
  return refreshing;
}

/** 确认手里有一枚可用的访问令牌：没有或快过期就用 Cookie 换一枚。返回是否已登录 */
export async function ensureAdminSession(): Promise<boolean> {
  if (accessToken && expiresAt - Date.now() > 30_000) return true;
  if (!accessToken && !hint()) return false;
  return !!(await refreshToken());
}

function goLogin(reason?: string) {
  const here = typeof location !== 'undefined' ? location.pathname + location.search : '/admin';
  const query: Record<string, string> = {};
  if (here.startsWith('/admin') && !here.startsWith('/admin/login')) query.redirect = here;
  if (reason) query.reason = reason;
  return navigateTo({ path: '/admin/login', query });
}

type FetchOptions = NonNullable<Parameters<typeof $fetch>[1]>;

export async function adminFetch<T = any>(path: string, opts: FetchOptions = {}): Promise<T> {
  const call = (token: string | null) =>
    $fetch<T>(path, {
      ...opts,
      headers: { ...(opts.headers as Record<string, string> | undefined), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    }) as Promise<T>;
  if (!accessToken || expiresAt - Date.now() < 30_000) await refreshToken();
  try {
    return await call(accessToken);
  } catch (err: any) {
    const status = err?.status ?? err?.statusCode ?? err?.response?.status;
    if (status === 401) {
      const fresh = await refreshToken();
      if (fresh) return await call(fresh);
      await goLogin('expired');
    }
    throw err;
  }
}

/** 退出当前会话；所有打开着的后台标签页一起回到登录页 */
export async function adminLogout(reason?: string) {
  try {
    await $fetch('/api/v1/admin/auth/logout', {
      method: 'POST',
      headers: { ...CLIENT_HEADER, ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
    });
  } catch {}
  forget();
  broadcastAdmin({ type: 'logout', reason });
  await navigateTo({ path: '/admin/login', query: reason ? { reason } : {} });
}

/** 从 FastAPI / 统一错误格式中取出可读的错误信息 */
export function apiErrorMessage(err: any, fallback = '操作失败，请稍后重试'): string {
  const d = err?.data;
  if (typeof d?.detail === 'string') return d.detail;
  return d?.error?.message || d?.message || fallback;
}
