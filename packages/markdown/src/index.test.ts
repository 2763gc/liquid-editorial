import { describe, it, expect } from 'vitest';
import { renderMarkdown, renderMarkdownDocument } from './index.js';

describe('Markdown Renderer', () => {
  it('renders standard markdown with headers and bold text', async () => {
    const html = await renderMarkdown('# Hello World\n\nThis is **bold** text.');
    expect(html).toContain('<h1 id="hello-world">Hello World</h1>');
    expect(html).toContain('<strong>bold</strong>');
  });

  it('renders code blocks with Shiki syntax highlighting', async () => {
    const html = await renderMarkdown('```ts\nconst x: number = 42;\n```');
    expect(html).toContain('class="shiki');
    expect(html).toContain('const');
  });

  it('renders terminal block', async () => {
    const html = await renderMarkdown('```terminal\n$ pnpm dev\n```');
    expect(html).toContain('terminal-block');
    expect(html).toContain('pnpm dev');
  });

  it('adds heading anchors and collects toc', async () => {
    const { html, toc } = await renderMarkdownDocument('## 存储引擎 Engine\n\n### LSM-Tree 结构');
    expect(html).toContain('id="存储引擎-engine"');
    expect(toc).toEqual([
      { level: 2, text: '存储引擎 Engine', anchor: '存储引擎-engine' },
      { level: 3, text: 'LSM-Tree 结构', anchor: 'lsm-tree-结构' },
    ]);
  });

  it('wraps code blocks with a header and copy button', async () => {
    const html = await renderMarkdown('```ts title="main.ts"\nconst a = 1;\n```');
    expect(html).toContain('class="code-block"');
    expect(html).toContain('main.ts');
    expect(html).toContain('data-copy');
  });

  it('transforms GitHub alerts correctly', async () => {
    const html = await renderMarkdown('> [!NOTE]\n> This is an important note.');
    expect(html).toContain('alert-callout alert-note');
  });
});

describe('Liquid Editorial v2 extensions', () => {
  it('joins terminal lines without blank lines between them (B43)', async () => {
    const html = await renderMarkdown('```terminal\n$ pnpm dev\nready in 300ms\n```');
    expect(html).toContain('</span><span class="term-line is-out">');
    expect(html).not.toMatch(/<\/span>\n<span class="term-line/);
  });

  it('numbers lines by default for blocks of six or more lines and honours noLineNumbers', async () => {
    const six = Array.from({ length: 6 }, (_, i) => `const v${i} = ${i};`).join('\n');
    expect(await renderMarkdown('```ts\n' + six + '\n```')).toContain('data-numbered');
    expect(await renderMarkdown('```ts noLineNumbers\n' + six + '\n```')).not.toContain('data-numbered');
    expect(await renderMarkdown('```ts showLineNumbers\nconst a = 1;\n```')).toContain('data-numbered');
  });

  it('renders code-group tabs from fence labels', async () => {
    const html = await renderMarkdown('::: code-group\n```bash [pnpm]\npnpm add gsap\n```\n```bash [npm]\nnpm i gsap\n```\n:::');
    expect(html).toContain('class="code-group"');
    expect(html).toContain('data-tabs="pnpm|npm"');
    expect(html).toContain('role="tabpanel"');
    expect(html.match(/role="tab"/g)?.length).toBe(2);
  });

  it('renders details containers', async () => {
    const html = await renderMarkdown('::: details 实现细节\n内容\n:::');
    expect(html).toContain('<details class="prose-details">');
    expect(html).toContain('实现细节');
  });

  it('renders footnotes as references with a notes section', async () => {
    const html = await renderMarkdown('正文[^1]\n\n[^1]: 旁注内容');
    expect(html).toContain('class="fn-ref"');
    expect(html).toContain('data-fn="1"');
    expect(html).toContain('class="footnotes"');
  });

  it('lifts a lone image out of its paragraph into a figure with width', async () => {
    const html = await renderMarkdown('![图](/a.png "图注"){width=wide}');
    expect(html).toContain('<figure class="prose-figure" data-width="wide">');
    expect(html).not.toContain('<p><figure');
  });
});
