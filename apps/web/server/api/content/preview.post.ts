import { createHash } from 'node:crypto';
import type { H3Event } from 'h3';
import { renderMarkdownDocument } from '@blog/markdown';

/**
 * 后台编辑器的实时预览：与前台文章页完全同一个渲染器（Shiki 只在服务端运行，浏览器不再下载高亮器）。
 * 只给已登录的编辑用：用请求里的 Bearer 令牌向 API 换一次身份，通过的结果只缓存 60 秒
 * （会话被吊销后，最多一分钟内预览也随之失效）。缓存键是令牌的哈希，不在内存里留原文。
 */
const verified = new Map<string, number>();
const TTL = 60 * 1000;
const MAX_BYTES = 600_000;

async function assertEditor(event: H3Event, auth: string | undefined) {
  if (!auth?.startsWith('Bearer ')) throw createError({ statusCode: 401, statusMessage: 'Unauthorized' });
  const key = createHash('sha256').update(auth).digest('hex');
  const hit = verified.get(key);
  if (hit && hit > Date.now()) return;
  try {
    await $fetch(`${apiBase()}/api/v1/admin/auth/me`, { headers: { authorization: auth, 'x-forwarded-for': forwardedFor(event) } });
  } catch {
    throw createError({ statusCode: 401, statusMessage: 'Unauthorized' });
  }
  if (verified.size > 200) verified.clear();
  verified.set(key, Date.now() + TTL);
}

export default defineEventHandler(async (event) => {
  await assertEditor(event, getRequestHeader(event, 'authorization'));
  const body = await readBody<{ markdown?: string }>(event);
  const markdown = String(body?.markdown ?? '');
  if (markdown.length > MAX_BYTES) throw createError({ statusCode: 413, statusMessage: '正文太长，预览上限约 60 万字符' });
  return renderMarkdownDocument(markdown);
});
