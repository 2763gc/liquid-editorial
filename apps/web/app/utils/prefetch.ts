/**
 * 悬停预取（PRD 11.1 · 任务书 §7）：鼠标停在链接上 100ms 后，提前请求目标页的数据。
 * 页面里用 prefetchJson 取数：命中进行中的请求就复用它，不会重复发起。
 */
const cache = new Map<string, { at: number; promise: Promise<unknown> }>();
const TTL = 60_000;

export function prefetchJson<T>(url: string): Promise<T> {
  const hit = cache.get(url);
  if (hit && Date.now() - hit.at < TTL) return hit.promise as Promise<T>;
  const promise = $fetch<T>(url).catch((err) => {
    cache.delete(url);
    throw err;
  });
  cache.set(url, { at: Date.now(), promise });
  return promise;
}

/** 链接 → 该页面主要数据的接口 */
export function dataUrlFor(href: string): string | null {
  const path = href.split(/[?#]/)[0];
  let m = path.match(/^\/posts\/([^/]+)$/);
  if (m) return `/api/content/posts/${m[1]}`;
  m = path.match(/^\/projects\/([^/]+)$/);
  if (m) return `/api/content/projects/${m[1]}`;
  m = path.match(/^\/series\/([^/]+)$/);
  if (m) return `/api/v1/series/${m[1]}`;
  return null;
}

export function prefetchRoute(href: string) {
  const url = dataUrlFor(href);
  if (url) prefetchJson(url).catch(() => {});
}
