import MarkdownIt, { type PluginSimple } from 'markdown-it';
import type StateBlock from 'markdown-it/lib/rules_block/state_block.mjs';
import footnote from 'markdown-it-footnote';
import { createHighlighter, type Highlighter } from 'shiki';
import {
  transformerNotationDiff,
  transformerNotationHighlight,
  transformerNotationFocus,
  transformerMetaHighlight,
} from '@shikijs/transformers';

/* ------------------------------------------------------------------ */
/* Shiki 单例                                                          */
/* ------------------------------------------------------------------ */

const LANGS = [
  'typescript', 'javascript', 'tsx', 'jsx', 'vue', 'python', 'json', 'html', 'css', 'scss',
  'bash', 'shell', 'sql', 'rust', 'go', 'java', 'kotlin', 'c', 'cpp', 'yaml', 'toml',
  'markdown', 'diff', 'dockerfile', 'nginx', 'ini',
];

const LANG_LABEL: Record<string, string> = {
  ts: 'TypeScript', typescript: 'TypeScript', js: 'JavaScript', javascript: 'JavaScript',
  tsx: 'TSX', jsx: 'JSX', vue: 'Vue', py: 'Python', python: 'Python', json: 'JSON',
  html: 'HTML', css: 'CSS', scss: 'SCSS', bash: 'Bash', sh: 'Shell', shell: 'Shell',
  sql: 'SQL', rust: 'Rust', rs: 'Rust', go: 'Go', java: 'Java', kotlin: 'Kotlin',
  c: 'C', cpp: 'C++', yaml: 'YAML', yml: 'YAML', toml: 'TOML', markdown: 'Markdown',
  md: 'Markdown', diff: 'Diff', dockerfile: 'Dockerfile', nginx: 'Nginx', ini: 'INI', text: 'Text',
};

/** 文件类型标记：两三个字母的铅字小标，不用图标字体也不用 emoji */
const LANG_MARK: Record<string, string> = {
  typescript: 'TS', javascript: 'JS', tsx: 'TSX', jsx: 'JSX', vue: 'VUE', python: 'PY', json: '{}',
  html: '<>', css: 'CSS', scss: 'SCSS', bash: '$', shell: '$', sql: 'SQL', rust: 'RS', go: 'GO',
  java: 'JV', kotlin: 'KT', c: 'C', cpp: 'C++', yaml: 'YML', toml: 'TML', markdown: 'MD', diff: '±',
  dockerfile: 'DK', nginx: 'NGX', ini: 'INI', text: 'TXT',
};

const LANG_ALIAS: Record<string, string> = {
  ts: 'typescript', js: 'javascript', py: 'python', sh: 'bash', zsh: 'bash', rs: 'rust',
  yml: 'yaml', md: 'markdown', docker: 'dockerfile',
};

let highlighterPromise: Promise<Highlighter> | null = null;

export function getHighlighterInstance(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ['github-light', 'github-dark-dimmed'],
      langs: LANGS,
    });
  }
  return highlighterPromise;
}

/* ------------------------------------------------------------------ */
/* 工具函数                                                            */
/* ------------------------------------------------------------------ */

export interface RenderOptions {
  mode?: 'full' | 'comment';
  allowHtml?: boolean;
}

export interface TocEntry {
  level: number;
  text: string;
  anchor: string;
}

export interface RenderResult {
  html: string;
  toc: TocEntry[];
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** 生成可读的锚点：保留中文与字母数字，其余转为连字符 */
export function headingSlug(text: string): string {
  const slug = text
    .trim()
    .toLowerCase()
    .replace(/[\s　]+/g, '-')
    .replace(/[^\p{L}\p{N}\-_]/gu, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return slug || 'section';
}

/** 解析 ```lang [标签] title="x" {1,3-4} showLineNumbers 形式的 info 字符串 */
export function parseFenceInfo(info: string) {
  const trimmed = info.trim();
  const lang = (trimmed.split(/[\s[{]/)[0] || '').toLowerCase();
  const meta = trimmed.slice(lang.length).trim();
  const titleMatch = meta.match(/title=["']([^"']+)["']/);
  const tabMatch = meta.match(/\[([^\]]+)\]/);
  return {
    lang,
    meta,
    title: titleMatch ? titleMatch[1] : '',
    tab: tabMatch ? tabMatch[1].trim() : '',
    numbers: /\bshowLineNumbers\b/.test(meta) ? true : /\bnoLineNumbers\b/.test(meta) ? false : null,
  };
}

/** 中英文之间插入细空格（U+2009）。在服务端完成，所有浏览器表现一致；CSS text-autospace 遇到细空格不会重复加距 */
function autoSpace(text: string): string {
  return text
    .replace(/([一-龥㐀-䶿])([A-Za-z0-9@#$%^&*+=\[(`])/g, '$1 $2')
    .replace(/([A-Za-z0-9!%&*)\]`])([一-龥㐀-䶿])/g, '$1 $2');
}

/* ------------------------------------------------------------------ */
/* ::: 容器（code-group / details）                                    */
/* ------------------------------------------------------------------ */

function containerPlugin(md: MarkdownIt) {
  function container(state: StateBlock, startLine: number, endLine: number, silent: boolean): boolean {
    const start = state.bMarks[startLine] + state.tShift[startLine];
    const max = state.eMarks[startLine];
    const line = state.src.slice(start, max);
    const m = line.match(/^:::\s*(code-group|details)\b\s*(.*)$/);
    if (!m) return false;
    if (silent) return true;

    // 找到配对的 :::（允许嵌套的 ::: 名称块）
    let depth = 1;
    let next = startLine;
    for (;;) {
      next++;
      if (next >= endLine) break;
      const s = state.bMarks[next] + state.tShift[next];
      const text = state.src.slice(s, state.eMarks[next]).trim();
      if (/^:::\s*\S/.test(text)) depth++;
      else if (text === ':::') {
        depth--;
        if (depth === 0) break;
      }
    }

    const kind = m[1].replace('-', '_');
    const open = state.push(`container_${kind}_open`, 'div', 1);
    open.info = m[2].trim();
    open.map = [startLine, next];
    open.block = true;

    const oldParent = state.parentType;
    const oldLineMax = state.lineMax;
    state.parentType = 'blockquote' as typeof state.parentType;
    state.lineMax = next;
    state.md.block.tokenize(state, startLine + 1, next);
    state.parentType = oldParent;
    state.lineMax = oldLineMax;

    const close = state.push(`container_${kind}_close`, 'div', -1);
    close.block = true;
    state.line = next + 1;
    return true;
  }

  md.block.ruler.before('fence', 'container', container, { alt: ['paragraph', 'reference', 'blockquote', 'list'] });

  md.renderer.rules.container_details_open = (tokens, idx) =>
    `<details class="prose-details"><summary><span class="prose-details-mark" aria-hidden="true"></span>${escapeHtml(tokens[idx].info || '展开')}</summary><div class="prose-details-body">\n`;
  md.renderer.rules.container_details_close = () => '</div></details>\n';

  // code-group：先在 core 阶段收集组内各代码块的标签，渲染时输出 tablist
  md.renderer.rules.container_code_group_open = (tokens, idx) => {
    const tabs: string[] = [];
    for (let i = idx + 1; i < tokens.length && tokens[i].type !== 'container_code_group_close'; i++) {
      if (tokens[i].type === 'fence') {
        const info = parseFenceInfo(tokens[i].info || '');
        tabs.push(info.tab || info.title || LANG_LABEL[info.lang] || info.lang || `#${tabs.length + 1}`);
      }
    }
    const buttons = tabs
      .map((t, i) => `<button type="button" role="tab" class="code-tab" data-tab="${escapeHtml(t)}" aria-selected="${i === 0}" tabindex="${i === 0 ? 0 : -1}">${escapeHtml(t)}</button>`)
      .join('');
    return `<div class="code-group" data-tabs="${escapeHtml(tabs.join('|'))}"><div class="code-tabs" role="tablist" aria-label="代码版本">${buttons}<span class="code-tab-ink" aria-hidden="true"></span></div>\n`;
  };
  md.renderer.rules.container_code_group_close = () => '</div>\n';
}

/* ------------------------------------------------------------------ */
/* 渲染器                                                              */
/* ------------------------------------------------------------------ */

const rendererCache = new Map<string, Promise<MarkdownIt>>();

async function buildRenderer(options: RenderOptions): Promise<MarkdownIt> {
  const isComment = options.mode === 'comment';
  const highlighter = await getHighlighterInstance();
  const loaded = new Set(highlighter.getLoadedLanguages());

  const md: MarkdownIt = new MarkdownIt({
    html: options.allowHtml ?? !isComment,
    linkify: true,
    typographer: false,
    breaks: isComment,
  });

  if (isComment) {
    md.disable(['heading', 'lheading', 'table', 'image']);
  } else {
    // @types/markdown-it-footnote 依赖另一版本的 @types/markdown-it，签名不兼容，按 PluginSimple 使用
    md.use(footnote as unknown as PluginSimple);
    containerPlugin(md);
  }

  /* ---- 代码块：完全接管 fence 渲染，输出带头部的 figure ---- */
  md.renderer.rules.fence = (tokens, idx) => {
    const token = tokens[idx];
    const { lang, meta, title, tab, numbers } = parseFenceInfo(token.info || '');
    const code = token.content.replace(/\n$/, '');
    let inGroup = false;
    for (let i = idx - 1; i >= 0; i--) {
      if (tokens[i].type === 'container_code_group_close') break;
      if (tokens[i].type === 'container_code_group_open') { inGroup = true; break; }
    }
    const tabAttr = inGroup ? ` data-tab="${escapeHtml(tab || title || LANG_LABEL[lang] || lang)}" role="tabpanel"` : '';

    if (lang === 'terminal' || lang === 'shell-session' || lang === 'console') {
      // 每行是 display:block 的 span，行与行之间不能再有换行符，否则会多出一个空行（B43）
      const lines = code.split('\n').map((line) => {
        if (/^\$\s?/.test(line)) {
          return `<span class="term-line is-cmd"><span class="term-prompt" aria-hidden="true">$</span>${escapeHtml(line.replace(/^\$\s?/, ''))}</span>`;
        }
        return `<span class="term-line is-out">${escapeHtml(line) || '&#8203;'}</span>`;
      });
      return `<figure class="terminal-block"${tabAttr}><figcaption class="terminal-header"><span class="terminal-dots" aria-hidden="true"><i></i><i></i><i></i></span><span class="terminal-title">${escapeHtml(title || 'terminal')}</span><button class="code-copy" type="button" data-copy aria-label="复制命令"><span class="code-copy-face">复制</span><span class="code-copy-face is-back" aria-hidden="true">已复制</span></button></figcaption><pre class="terminal-body"><code>${lines.join('')}</code></pre></figure>\n`;
    }

    if (lang === 'mermaid') {
      return `<figure class="mermaid-block"${tabAttr}><figcaption class="code-head"><span class="code-mark" aria-hidden="true">◇</span><span class="code-lang">Diagram</span></figcaption><pre class="mermaid">${escapeHtml(code)}</pre></figure>\n`;
    }

    const resolved = LANG_ALIAS[lang] || lang;
    const validLang = loaded.has(resolved) ? resolved : 'text';
    let body: string;
    try {
      body = highlighter.codeToHtml(code, {
        lang: validLang,
        themes: { light: 'github-light', dark: 'github-dark-dimmed' },
        defaultColor: 'light',
        meta: { __raw: meta },
        transformers: [
          transformerNotationDiff({ matchAlgorithm: 'v3' }),
          transformerNotationHighlight({ matchAlgorithm: 'v3' }),
          transformerNotationFocus({ matchAlgorithm: 'v3' }),
          transformerMetaHighlight(),
        ],
      });
    } catch {
      body = `<pre class="shiki"><code>${escapeHtml(code)}</code></pre>`;
    }

    const label = LANG_LABEL[lang] || (lang ? lang.toUpperCase() : 'Text');
    const mark = LANG_MARK[validLang] || (lang ? lang.slice(0, 3).toUpperCase() : 'TXT');
    const lineCount = code.split('\n').length;
    // 行号：显式 showLineNumbers / noLineNumbers 优先；否则 6 行以上的代码默认显示
    const numbered = !isComment && (numbers ?? lineCount >= 6);
    const head = `<figcaption class="code-head"><span class="code-mark" aria-hidden="true">${escapeHtml(mark)}</span><span class="code-lang">${escapeHtml(label)}</span>${title ? `<span class="code-title">${escapeHtml(title)}</span>` : ''}<span class="code-tools">${isComment ? '' : '<button class="code-wrap" type="button" data-wrap aria-pressed="false" title="自动换行">换行</button>'}<button class="code-copy" type="button" data-copy aria-label="复制代码"><span class="code-copy-face">复制</span><span class="code-copy-face is-back" aria-hidden="true">已复制</span></button></span></figcaption>`;
    const collapsible = !isComment && lineCount > 30 ? ' data-collapsible' : '';
    const numberedAttr = numbered ? ' data-numbered' : '';
    const digits = String(lineCount).length;
    return `<figure class="code-block" data-lang="${escapeHtml(validLang)}" data-lines="${lineCount}" style="--ln-digits:${digits}"${numberedAttr}${collapsible}${tabAttr}>${head}<div class="code-body">${body}</div></figure>\n`;
  };

  /* ---- 标题锚点 + 目录收集 ---- */
  md.renderer.rules.heading_open = (tokens, idx, opts, env, self) => {
    const token = tokens[idx];
    const level = Number(token.tag.slice(1));
    const inline = tokens[idx + 1];
    const text = (inline?.children || [])
      .filter((t) => t.type === 'text' || t.type === 'code_inline')
      .map((t) => t.content)
      .join('')
      .replace(/ /g, ' ')
      .trim();
    const used: Map<string, number> = env.__slugs || (env.__slugs = new Map());
    let anchor = headingSlug(text);
    const count = used.get(anchor) || 0;
    used.set(anchor, count + 1);
    if (count > 0) anchor = `${anchor}-${count}`;
    token.attrSet('id', anchor);
    if (level === 2 || level === 3) {
      (env.toc as TocEntry[] | undefined)?.push({ level, text, anchor });
    }
    return self.renderToken(tokens, idx, opts);
  };

  md.renderer.rules.heading_close = (tokens, idx, opts, _env, self) => {
    const open = tokens[idx - 2];
    const level = Number(tokens[idx].tag.slice(1));
    const id = open?.attrGet('id');
    const anchor = id && level >= 2 && level <= 3 && !isComment
      ? `<a class="heading-anchor" href="#${id}" aria-label="复制本节链接">#</a>`
      : '';
    return anchor + self.renderToken(tokens, idx, opts);
  };

  /* ---- 文本节点：中英文间距 ---- */
  const defaultText = md.renderer.rules.text!;
  md.renderer.rules.text = (tokens, idx, opts, env, self) => {
    tokens[idx].content = autoSpace(tokens[idx].content);
    return defaultText(tokens, idx, opts, env, self);
  };

  /* ---- 表格：外包一层可横向滚动的容器 ---- */
  md.renderer.rules.table_open = () => '<div class="table-wrap" data-lenis-prevent-horizontal><table>\n';
  md.renderer.rules.table_close = () => '</table></div>\n';

  /* ---- 链接：外链新窗口 + 标记 ---- */
  const defaultLinkOpen = md.renderer.rules.link_open
    || ((tokens, idx, opts, _env, self) => self.renderToken(tokens, idx, opts));
  md.renderer.rules.link_open = (tokens, idx, opts, env, self) => {
    const href = tokens[idx].attrGet('href') || '';
    if (/^https?:\/\//i.test(href)) {
      tokens[idx].attrSet('target', '_blank');
      tokens[idx].attrSet('rel', isComment ? 'noopener noreferrer nofollow ugc' : 'noopener noreferrer');
      tokens[idx].attrJoin('class', 'ext-link');
      if (!isComment) tokens[idx].attrSet('data-cursor', 'external');
    }
    return defaultLinkOpen(tokens, idx, opts, env, self);
  };

  /* ---- 图片：懒加载 + 图注 + {width=wide|full} ---- */
  md.core.ruler.after('inline', 'image_block', (state) => {
    const tokens = state.tokens;
    for (let t = 0; t < tokens.length; t++) {
      const children = tokens[t].children;
      if (!children) continue;
      for (let i = 0; i < children.length - 1; i++) {
        if (children[i].type !== 'image') continue;
        const next = children[i + 1];
        const m = next.type === 'text' && next.content.match(/^\{width=(normal|wide|full)\}/);
        if (!m) continue;
        children[i].attrSet('data-width', m[1]);
        next.content = next.content.slice(m[0].length);
      }
      // 段落里只有一张图：去掉 <p>，整体输出为 <figure>（figure 不能嵌在 p 里，否则解析后结构变化导致水合不一致）
      const meaningful = children.filter((c) => !(c.type === 'text' && !c.content.trim()) && c.type !== 'softbreak');
      if (meaningful.length === 1 && meaningful[0].type === 'image' && tokens[t - 1]?.type === 'paragraph_open') {
        meaningful[0].attrSet('data-block', '1');
        tokens[t - 1].hidden = true;
        if (tokens[t + 1]?.type === 'paragraph_close') tokens[t + 1].hidden = true;
      }
    }
  });
  md.renderer.rules.image = (tokens, idx) => {
    const token = tokens[idx];
    const src = token.attrGet('src') || '';
    const alt = token.content || '';
    const title = token.attrGet('title') || '';
    const width = token.attrGet('data-width') || 'normal';
    const img = `<img src="${escapeHtml(src)}" alt="${escapeHtml(alt)}" loading="lazy" decoding="async" data-cursor="zoom">`;
    if (!token.attrGet('data-block')) return img;
    return `<figure class="prose-figure" data-width="${width}">${img}${title ? `<figcaption>${escapeHtml(title)}</figcaption>` : ''}</figure>\n`;
  };

  /* ---- 脚注：桌面端由前台排成页边旁注，这里输出可独立阅读的语义结构 ---- */
  if (!isComment) {
    md.renderer.rules.footnote_caption = (tokens, idx) => String(Number(tokens[idx].meta.id) + 1);
    md.renderer.rules.footnote_ref = (tokens, idx, opts, env, self) => {
      const id = self.rules.footnote_anchor_name!(tokens, idx, opts, env, self);
      const n = Number(tokens[idx].meta.id) + 1;
      const sub = tokens[idx].meta.subId > 0 ? `:${tokens[idx].meta.subId}` : '';
      return `<sup class="fn-ref"><a href="#fn${id}" id="fnref${id}${sub}" data-fn="${id}" aria-describedby="fn${id}">${n}</a></sup>`;
    };
    md.renderer.rules.footnote_block_open = () => '<section class="footnotes" aria-label="脚注"><p class="footnotes-title">注</p><ol class="footnotes-list">\n';
    md.renderer.rules.footnote_anchor = (tokens, idx, opts, env, self) => {
      const id = self.rules.footnote_anchor_name!(tokens, idx, opts, env, self);
      return ` <a href="#fnref${id}" class="footnote-backref" aria-label="回到正文">↩</a>`;
    };
  }

  /* ---- GitHub Alerts ---- */
  md.core.ruler.after('block', 'github_alerts', (state) => {
    const tokens = state.tokens;
    for (let i = 0; i < tokens.length; i++) {
      if (tokens[i].type !== 'blockquote_open') continue;
      const contentToken = tokens[i + 2];
      if (tokens[i + 1]?.type !== 'paragraph_open' || contentToken?.type !== 'inline') continue;
      const match = contentToken.content.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i);
      if (!match) continue;
      const alertType = match[1].toLowerCase();
      contentToken.content = contentToken.content.slice(match[0].length);
      tokens[i].attrJoin('class', `alert-callout alert-${alertType}`);
      tokens[i].attrSet('data-label', ({ note: '注意', tip: '提示', important: '重要', warning: '警告', caution: '危险' } as Record<string, string>)[alertType] || alertType);
    }
  });

  return md;
}

function getRenderer(options: RenderOptions): Promise<MarkdownIt> {
  const key = `${options.mode || 'full'}:${options.allowHtml ?? 'default'}`;
  let renderer = rendererCache.get(key);
  if (!renderer) {
    renderer = buildRenderer(options);
    rendererCache.set(key, renderer);
  }
  return renderer;
}

/** 渲染 Markdown，同时返回目录（二、三级标题） */
export async function renderMarkdownDocument(content: string, options: RenderOptions = {}): Promise<RenderResult> {
  const md = await getRenderer(options);
  const env: { toc: TocEntry[] } = { toc: [] };
  const html = md.render(content || '', env);
  return { html, toc: env.toc };
}

export async function renderMarkdown(content: string, options: RenderOptions = {}): Promise<string> {
  return (await renderMarkdownDocument(content, options)).html;
}

/** 兼容旧接口 */
export async function createMarkdownRenderer(options: RenderOptions = {}): Promise<MarkdownIt> {
  return getRenderer(options);
}
