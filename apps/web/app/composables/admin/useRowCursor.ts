import { ref, watch, nextTick, onMounted, onBeforeUnmount, type Ref } from 'vue';

/**
 * 列表的键盘光标：j / k（或 ↓ / ↑）移动，回车打开，/ 聚焦搜索框；额外的单键动作由 actions 提供。
 * 光标行带 .is-cursor（左侧一道墨线），滚动跟随但不跳动。输入框内不响应。
 */
export function useRowCursor<T>(rows: Ref<T[]>, opts: {
  onOpen: (row: T) => void;
  actions?: Record<string, (row: T) => void>;
  searchSelector?: string;
  scope?: Ref<HTMLElement | null>;
}) {
  const cursor = ref(-1);

  watch(() => rows.value.length, (n) => {
    if (cursor.value >= n) cursor.value = n - 1;
  });

  function isTyping(e: KeyboardEvent) {
    const t = e.target as HTMLElement | null;
    return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);
  }

  function reveal() {
    nextTick(() => opts.scope?.value?.querySelector<HTMLElement>('.is-cursor')?.scrollIntoView({ block: 'nearest' }));
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e) || document.querySelector('.cmd-scrim, .a-modal-backdrop, .a-drawer-backdrop')) return;
    const n = rows.value.length;
    if (e.key === '/' && opts.searchSelector) {
      const el = document.querySelector<HTMLInputElement>(opts.searchSelector);
      if (el) {
        e.preventDefault();
        el.focus();
      }
      return;
    }
    if (!n) return;
    if (e.key === 'j' || e.key === 'ArrowDown') {
      e.preventDefault();
      cursor.value = Math.min(n - 1, cursor.value + 1);
      reveal();
    } else if (e.key === 'k' || e.key === 'ArrowUp') {
      e.preventDefault();
      cursor.value = Math.max(0, cursor.value - 1);
      reveal();
    } else if (e.key === 'Enter' && cursor.value >= 0) {
      e.preventDefault();
      opts.onOpen(rows.value[cursor.value]);
    } else if (cursor.value >= 0 && opts.actions?.[e.key]) {
      e.preventDefault();
      opts.actions[e.key](rows.value[cursor.value]);
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown));
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
  return { cursor };
}
