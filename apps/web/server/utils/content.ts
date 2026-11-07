import { renderMarkdownDocument, type RenderResult } from '@blog/markdown';

/**
 * 服务端 Markdown 渲染缓存
 * Shiki 只在 Nitro 服务端运行，浏览器端不再下载高亮器与 wasm。
 */
const cache = new Map<string, RenderResult>();
const MAX_ENTRIES = 200;

export async function renderCached(key: string, markdown: string): Promise<RenderResult> {
  const cacheKey = `${key}:${markdown.length}:${hash(markdown)}`;
  const hit = cache.get(cacheKey);
  if (hit) return hit;
  const result = await renderMarkdownDocument(markdown);
  if (cache.size >= MAX_ENTRIES) {
    const oldest = cache.keys().next().value;
    if (oldest) cache.delete(oldest);
  }
  cache.set(cacheKey, result);
  return result;
}

function hash(str: string): string {
  let h = 5381;
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function apiBase(): string {
  return process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';
}

/** 透传后端错误状态码，避免把 404 变成 500 */
export async function fetchApi<T>(path: string, event: any): Promise<T> {
  try {
    const headers: Record<string, string> = { 'user-agent': getRequestHeader(event, 'user-agent') || '' };
    headers['x-forwarded-for'] = forwardedFor(event);
    return await $fetch<T>(`${apiBase()}${path}`, { headers });
  } catch (err: any) {
    const status = err?.response?.status || err?.statusCode || 502;
    throw createError({ statusCode: status, statusMessage: status === 404 ? 'Not Found' : 'Upstream Error' });
  }
}
