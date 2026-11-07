/** 全站共用的展示格式化（Nuxt 自动导入） */

/** 2026-08-27T… → 2026.08.27 */
export function dotDate(iso?: string | null): string {
  if (!iso) return '';
  const d = iso.slice(0, 10).split('-');
  return d.length === 3 ? `${d[0]}.${d[1]}.${d[2]}` : iso;
}

/** 期号：1 → 001 */
export function issueNo(n?: number | null, width = 3): string {
  return String(n ?? 0).padStart(width, '0');
}

/**
 * 把摘要 / Markdown 片段整理成一段干净的纯文本：
 * 去掉代码块、GitHub Alert 标记（[!NOTE]）、Markdown 符号与字面量 \n，合并空白。
 */
export function plainText(md?: string | null, max = 0): string {
  const text = (md || '')
    .replace(/\\n/g, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/gi, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+/gm, '')
    .replace(/[*_~]{1,3}/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return max && text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

/** 相对时间：刚刚 / 5 分钟前 / 3 小时前 / 2 天前，超过 30 天显示日期 */
export function timeAgo(iso?: string | null, now = Date.now()): string {
  if (!iso) return '';
  const t = new Date(/Z|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`).getTime();
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, (now - t) / 1000);
  if (s < 60) return '刚刚';
  if (s < 3600) return `${Math.floor(s / 60)} 分钟前`;
  if (s < 86400) return `${Math.floor(s / 3600)} 小时前`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} 天前`;
  return dotDate(iso);
}

/** 字节数 → 1.2 KB / 3.4 MB */
export function fileSize(bytes?: number | null): string {
  const b = bytes ?? 0;
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(b < 10240 ? 1 : 0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

/** 1234 → 1,234；12345 → 1.2 万 */
export function compactNumber(n?: number | null): string {
  const v = n ?? 0;
  if (v >= 10000) return `${(v / 10000).toFixed(v >= 100000 ? 0 : 1)} 万`;
  return v.toLocaleString('zh-CN');
}
