import { onMounted, onBeforeUnmount, type Ref } from 'vue';
import gsap from 'gsap';
import { useLenis } from '~/composables/useLenis';

/**
 * 正文增强（事件委托，服务端渲染的 HTML 不需要水合任何组件）
 * - 代码块：复制（按钮翻牌成「已复制」；在代码区单击、且没有选中文字时也复制）、自动换行（全站记忆）、长代码展开
 * - code-group：标签页切换，读者的选择全站记忆（选了 pnpm，其他文章里的 pnpm 也会被选中）
 * - 标题锚点：复制本节链接
 * - 图片：交给 onImage 打开灯箱
 */
const WRAP_KEY = 'blog_code_wrap';
const TAB_KEY = 'blog_code_tab';

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  }
}

function codeOf(fig: Element) {
  if (fig.classList.contains('terminal-block')) {
    return Array.from(fig.querySelectorAll('.term-line.is-cmd')).map((l) => (l.textContent || '').trim()).join('\n');
  }
  const lines = fig.querySelectorAll('.line:not(.diff.remove)');
  return lines.length ? Array.from(lines).map((l) => l.textContent || '').join('\n') : fig.querySelector('pre')?.textContent || '';
}

export function useProse(rootRef: Ref<HTMLElement | null>, opts: { onImage?: (img: HTMLImageElement) => void; announce?: (msg: string) => void } = {}) {
  const timers = new Set<number>();

  function flash(btn: HTMLElement) {
    btn.classList.add('is-copied');
    const t = window.setTimeout(() => {
      btn.classList.remove('is-copied');
      timers.delete(t);
    }, 1600);
    timers.add(t);
  }

  async function copyFrom(fig: Element) {
    const ok = await copyText(codeOf(fig));
    const btn = fig.querySelector<HTMLElement>('[data-copy]');
    if (btn && ok) flash(btn);
    opts.announce?.(ok ? '代码已复制' : '复制失败');
  }

  function setWrap(on: boolean, scope: ParentNode = document) {
    scope.querySelectorAll<HTMLElement>('figure.code-block').forEach((fig) => {
      fig.classList.toggle('is-wrapped', on);
      fig.querySelector('[data-wrap]')?.setAttribute('aria-pressed', String(on));
    });
  }

  function selectTab(group: Element, label: string, remember = true) {
    const tabs = Array.from(group.querySelectorAll<HTMLButtonElement>('.code-tab'));
    const panels = Array.from(group.querySelectorAll<HTMLElement>(':scope > figure'));
    let idx = tabs.findIndex((t) => t.dataset.tab === label);
    if (idx < 0) idx = 0;
    tabs.forEach((t, i) => {
      t.setAttribute('aria-selected', String(i === idx));
      t.tabIndex = i === idx ? 0 : -1;
    });
    panels.forEach((p, i) => p.classList.toggle('is-active', i === idx));
    // 朱砂下划线滑到选中的标签
    const tab = tabs[idx];
    const ink = group.querySelector<HTMLElement>('.code-tab-ink');
    if (tab && ink) {
      ink.style.setProperty('--tab-x', `${tab.offsetLeft}px`);
      ink.style.setProperty('--tab-w', `${tab.offsetWidth}px`);
    }
    if (remember && tab) {
      try { localStorage.setItem(TAB_KEY, tab.dataset.tab || ''); } catch {}
    }
  }

  function enhance() {
    const root = rootRef.value;
    if (!root) return;
    let wrap = false;
    let tab = '';
    try {
      wrap = localStorage.getItem(WRAP_KEY) === '1';
      tab = localStorage.getItem(TAB_KEY) || '';
    } catch {}
    setWrap(wrap, root);
    root.querySelectorAll('.code-group').forEach((g) => selectTab(g, tab, false));
    root.querySelectorAll<HTMLElement>('figure.code-block[data-collapsible]').forEach((fig) => {
      if (fig.querySelector('.code-expand')) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'code-expand';
      btn.textContent = `展开全部 ${fig.getAttribute('data-lines')} 行`;
      fig.appendChild(btn);
    });
  }

  function onClick(e: MouseEvent) {
    const target = e.target as HTMLElement;

    const copyBtn = target.closest<HTMLElement>('[data-copy]');
    if (copyBtn) {
      const fig = copyBtn.closest('figure');
      if (fig) copyFrom(fig);
      return;
    }

    const wrapBtn = target.closest<HTMLElement>('[data-wrap]');
    if (wrapBtn) {
      const on = wrapBtn.getAttribute('aria-pressed') !== 'true';
      setWrap(on);
      try { localStorage.setItem(WRAP_KEY, on ? '1' : '0'); } catch {}
      gsap.delayedCall(0, () => useLenis().getLenis()?.resize());
      return;
    }

    const tabBtn = target.closest<HTMLButtonElement>('.code-tab');
    if (tabBtn) {
      const label = tabBtn.dataset.tab || '';
      // 全站记忆：同一页所有包含这个标签的分组一起切换
      document.querySelectorAll('.code-group').forEach((g) => {
        if (g.querySelector(`.code-tab[data-tab="${CSS.escape(label)}"]`)) selectTab(g, label, g === tabBtn.closest('.code-group'));
      });
      return;
    }

    const expand = target.closest<HTMLElement>('.code-expand');
    if (expand) {
      const fig = expand.closest('figure')!;
      const expanded = fig.classList.toggle('is-expanded');
      expand.textContent = expanded ? '收起' : `展开全部 ${fig.getAttribute('data-lines')} 行`;
      if (!expanded) useLenis().scrollTo(fig as HTMLElement, { offset: -120 });
      gsap.delayedCall(0, () => useLenis().getLenis()?.resize());
      return;
    }

    const anchor = target.closest<HTMLAnchorElement>('.heading-anchor');
    if (anchor) {
      e.preventDefault();
      const id = decodeURIComponent(anchor.hash.slice(1));
      copyText(`${location.origin}${location.pathname}#${encodeURIComponent(id)}`);
      history.replaceState(history.state, '', `#${encodeURIComponent(id)}`);
      const h = document.getElementById(id);
      if (h) useLenis().scrollTo(h, { offset: -96 });
      opts.announce?.('本节链接已复制');
      return;
    }

    const img = target.closest<HTMLImageElement>('img');
    if (img && opts.onImage) {
      opts.onImage(img);
      return;
    }

    // 在代码区单击（不是拖选文字）也复制
    const body = target.closest('.code-body, .terminal-body');
    if (body) {
      const sel = document.getSelection();
      if (sel && !sel.isCollapsed) return;
      const fig = body.closest('figure');
      if (fig) copyFrom(fig);
    }
  }

  function onKeydown(e: KeyboardEvent) {
    const tab = (e.target as HTMLElement).closest<HTMLButtonElement>('.code-tab');
    if (!tab || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft')) return;
    const tabs = Array.from(tab.parentElement?.querySelectorAll<HTMLButtonElement>('.code-tab') || []);
    const i = tabs.indexOf(tab);
    const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length];
    next?.focus();
    next?.click();
    e.preventDefault();
  }

  onMounted(() => {
    rootRef.value?.addEventListener('click', onClick);
    rootRef.value?.addEventListener('keydown', onKeydown);
  });
  onBeforeUnmount(() => {
    rootRef.value?.removeEventListener('click', onClick);
    rootRef.value?.removeEventListener('keydown', onKeydown);
    timers.forEach((t) => window.clearTimeout(t));
  });

  return { enhance, copyText };
}
