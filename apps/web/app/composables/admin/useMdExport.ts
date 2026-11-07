import { getMdTheme, mdPaperClass, ensureMdThemeFont } from '~/utils/mdThemes';

/**
 * Markdown 文稿导出：PDF（浏览器打印为矢量 PDF）/ 独立 HTML / Markdown 源文件。
 *
 * 导出文档是一个自包含的 HTML：内联当前页面已加载的全部同源样式（站点 Token、代码块、排版主题），
 * 跨域的字体样式表以 <link> 引入；图片地址转为绝对地址。PDF 通过隐藏 iframe 打印该文档，
 * 文字保持可选择、可搜索，字体与配色与预览完全一致。
 */
export interface MdDoc {
  themeId: string;
  title: string;
  subtitle?: string;
  kicker?: string;
  meta?: string;
  /** 渲染后的正文 HTML */
  html: string;
  /** Markdown 原文（导出 .md 用） */
  markdown: string;
  /** 刊物主题跟随文章强调色 */
  accent?: string;
  essay?: boolean;
}

export interface MdExportOptions {
  paper: 'A4' | 'A5' | 'Letter';
  margin: 'normal' | 'narrow' | 'wide';
  pageNumbers: boolean;
  includeTitle: boolean;
}

export const DEFAULT_EXPORT_OPTIONS: MdExportOptions = { paper: 'A4', margin: 'normal', pageNumbers: true, includeTitle: true };

const MARGINS: Record<MdExportOptions['margin'], string> = {
  narrow: '12mm 12mm 14mm',
  normal: '18mm 17mm 20mm',
  wide: '24mm 24mm 26mm',
};

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

/** 标题区 HTML：预览与导出共用同一份结构，主题样式才能一致 */
export function mdHeadHtml(doc: Pick<MdDoc, 'title' | 'subtitle' | 'kicker' | 'meta'>): string {
  return [
    '<header class="mdt-head">',
    doc.kicker ? `<p class="mdt-kicker">${esc(doc.kicker)}</p>` : '',
    `<h1 class="mdt-title">${esc(doc.title || '未命名文稿')}</h1>`,
    doc.subtitle ? `<p class="mdt-sub">${esc(doc.subtitle)}</p>` : '',
    doc.meta ? `<p class="mdt-meta">${esc(doc.meta)}</p>` : '',
    '</header>',
  ].join('');
}

/** 把样式表里的相对 url() 改为以样式表地址为基准的绝对地址 */
function rebaseUrls(css: string, base: string): string {
  return css.replace(/url\(\s*(['"]?)(?!data:|https?:|blob:|#)([^'")]+)\1\s*\)/g, (_m, q, p) => {
    try { return `url(${q}${new URL(p, base).href}${q})`; } catch { return _m; }
  });
}

/**
 * 按层叠顺序收集当前页面的样式原文：<style> 直接取文本，同源 <link> 拉取原文件，
 * 跨域样式表（Google Fonts、字体 CDN）保留为 <link>。
 * 不能用 cssRule.cssText：同一规则里「含 var() 的简写 + 之后覆盖其中某个长写」（如 background: var(--x) 再写 background-clip: text）
 * 会被浏览器序列化成一串空值长写，导出后这些样式会整段丢失。
 */
async function collectStyles(): Promise<string> {
  const parts: string[] = [];
  for (const node of Array.from(document.querySelectorAll<HTMLStyleElement | HTMLLinkElement>('style, link[rel="stylesheet"]'))) {
    if (node instanceof HTMLStyleElement) {
      // 开发环境注入的样式带内联 sourcemap，导出时去掉
      const text = (node.textContent || '').replace(/\/\*# sourceMappingURL=[^*]*\*\//g, '');
      if (text.trim()) parts.push(`<style>${text}</style>`);
      continue;
    }
    const href = node.href;
    if (!href) continue;
    if (new URL(href).origin !== location.origin) {
      parts.push(`<link rel="stylesheet" href="${esc(href)}">`);
      continue;
    }
    try {
      const text = await fetch(href).then((r) => (r.ok ? r.text() : ''));
      if (text) parts.push(`<style>${rebaseUrls(text, href)}</style>`);
    } catch {
      parts.push(`<link rel="stylesheet" href="${esc(href)}">`);
    }
  }
  return parts.join('\n');
}

/**
 * 图片与链接改为绝对地址，去掉懒加载（隐藏 iframe 里的懒加载图片不会加载）。
 * 注意 <template> 的内容文档没有基准地址，img.src 不会被解析，必须显式以当前页面地址为基准。
 */
function absolutize(html: string): string {
  const tpl = document.createElement('template');
  tpl.innerHTML = html;
  const abs = (v: string | null) => {
    try { return v ? new URL(v, location.href).href : v; } catch { return v; }
  };
  tpl.content.querySelectorAll('img').forEach((img) => {
    const src = abs(img.getAttribute('src'));
    if (src) img.setAttribute('src', src);
    img.removeAttribute('loading');
  });
  tpl.content.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (href && !href.startsWith('#')) a.setAttribute('href', abs(href)!);
  });
  return tpl.innerHTML;
}

export async function buildMdDocument(doc: MdDoc, opts: MdExportOptions = DEFAULT_EXPORT_OPTIONS): Promise<string> {
  const theme = getMdTheme(doc.themeId);
  ensureMdThemeFont(theme);
  const styles = await collectStyles();
  const [paperBg] = theme.swatch;
  const pageNumber = opts.pageNumbers
    ? `@bottom-center { content: counter(page) " / " counter(pages); font-family: "Inter", "PingFang SC", sans-serif; font-size: 8.5pt; color: ${theme.tone === 'dark' ? '#6B7180' : '#9A958B'}; }`
    : '';
  const paperClasses = [mdPaperClass(theme.id), theme.id === 'site' && doc.essay ? 'prose-essay' : ''].filter(Boolean).join(' ');
  const style = theme.id === 'site' && doc.accent ? ` style="--color-accent: ${esc(doc.accent)}"` : '';
  const body = (opts.includeTitle ? mdHeadHtml(doc) : '') + absolutize(doc.html);

  // @page 背景让页边距也铺上纸色，否则浅色纸面会被白色页边框住
  const exportCss = `
@page { size: ${opts.paper}; margin: ${MARGINS[opts.margin]}; background: ${paperBg}; ${pageNumber} }
html, body { margin: 0; padding: 0; background: ${paperBg}; }
body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.md-paper { box-sizing: border-box; max-width: 820px; min-height: 100vh; margin: 0 auto; padding: 64px 56px 80px; }
@media print {
  .md-paper { max-width: none; min-height: 0; padding: 0; }
  .md-paper :is(h1, h2, h3, h4, h5, h6) { break-after: avoid-page; }
  .md-paper :is(blockquote, img, .prose-figure, tr, .alert-callout, .mermaid-block, .mdt-head) { break-inside: avoid; }
  .md-paper :is(.code-head, .terminal-header) { break-after: avoid; }
  .md-paper :is(pre, .table-wrap, .code-body) { overflow: visible !important; }
  .md-paper pre code { min-width: 0 !important; }
  .md-paper :is(.code-block .line, .term-line) { white-space: pre-wrap !important; word-break: break-word; }
}`;

  return `<!doctype html>
<html lang="zh-CN" data-theme="${theme.tone}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="Luntrix Editorial · ${esc(theme.name)}">
<title>${esc(doc.title || '未命名文稿')}</title>
${styles}
<style>${exportCss}</style>
</head>
<body>
<article class="${paperClasses}" data-code="${theme.code}"${style}>${body}</article>
</body>
</html>`;
}

export function safeFilename(name: string, fallback = 'untitled'): string {
  const s = (name || '').replace(/[\\/:*?"<>|\n\r\t]+/g, ' ').trim().slice(0, 80);
  return s || fallback;
}

function download(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function exportHtml(doc: MdDoc, opts?: MdExportOptions) {
  download(await buildMdDocument(doc, opts), `${safeFilename(doc.title)}.html`, 'text/html;charset=utf-8');
}

export function exportMarkdown(doc: MdDoc) {
  const head = [doc.title ? `# ${doc.title}` : '', doc.subtitle ? `> ${doc.subtitle}` : ''].filter(Boolean).join('\n\n');
  const text = head ? `${head}\n\n${doc.markdown.replace(/^\s+/, '')}` : doc.markdown;
  download(text.endsWith('\n') ? text : `${text}\n`, `${safeFilename(doc.title)}.md`, 'text/markdown;charset=utf-8');
}

/**
 * 打印为 PDF：在隐藏 iframe 中载入导出文档，等字体与图片就绪后调起打印。
 * 打印对话框里选择「另存为 PDF」即可得到矢量 PDF；文件名默认取文章标题。
 */
export async function exportPdf(doc: MdDoc, opts: MdExportOptions = DEFAULT_EXPORT_OPTIONS): Promise<void> {
  const html = await buildMdDocument(doc, opts);
  const iframe = document.createElement('iframe');
  iframe.setAttribute('aria-hidden', 'true');
  iframe.style.cssText = 'position:fixed;left:-10000px;top:0;width:820px;height:1200px;border:0;opacity:0;pointer-events:none;';
  document.body.appendChild(iframe);

  try {
    await new Promise<void>((resolve) => {
      iframe.onload = () => resolve();
      iframe.srcdoc = html;
    });
    const win = iframe.contentWindow!;
    const idoc = iframe.contentDocument!;
    // 图片解码完成、网络字体加载完成后再打印，避免 PDF 里出现回退字体或空白图片
    await Promise.all(Array.from(idoc.images).map((img) => (img.complete ? Promise.resolve() : new Promise((r) => { img.onload = img.onerror = r; }))));
    await Promise.race([idoc.fonts?.ready, new Promise((r) => setTimeout(r, 6000))]);
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    const prevTitle = document.title;
    document.title = safeFilename(doc.title);
    win.focus();
    win.print();
    document.title = prevTitle;
  } finally {
    setTimeout(() => iframe.remove(), 1500);
  }
}
