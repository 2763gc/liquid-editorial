<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import { Search, CornerDownLeft, FileText } from 'lucide-vue-next';
import { useAdminCommands, type AdminCommand } from '~/composables/admin/useAdminCommands';
import { adminFetch } from '~/composables/admin/useAdminApi';
import { lockScroll, unlockScroll } from '~/composables/useLenis';

/**
 * 后台命令面板（⌘K）：前往栏目、执行动作、按标题直达特稿。
 * 全程键盘：↑↓ 选择，回车执行，Esc 关闭。命中的字用一道墨线标出。
 */
const commands = useAdminCommands();
const router = useRouter();
const query = ref('');
const cursor = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);
const listRef = ref<HTMLElement | null>(null);
const postHits = ref<AdminCommand[]>([]);
const searching = ref(false);
let searchTimer: ReturnType<typeof setTimeout> | undefined;
let searchSeq = 0;

function match(c: AdminCommand, q: string) {
  if (!q) return true;
  const hay = `${c.label} ${c.group} ${c.keywords || ''} ${c.hint || ''}`.toLowerCase();
  return q.toLowerCase().split(/\s+/).every((w) => hay.includes(w));
}

const results = computed(() => {
  const q = query.value.trim();
  const local = commands.all.value.filter((c) => match(c, q));
  return [...local, ...postHits.value];
});
const grouped = computed(() => {
  const out: Array<{ group: string; items: Array<AdminCommand & { index: number }> }> = [];
  results.value.forEach((c, index) => {
    let g = out.find((x) => x.group === c.group);
    if (!g) out.push((g = { group: c.group, items: [] }));
    g.items.push({ ...c, index });
  });
  return out;
});

/** 命中的字加一道墨线；先整体转义，杜绝注入 */
function highlight(text: string) {
  const esc = text.replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]!));
  const q = query.value.trim();
  if (!q) return esc;
  const words = q.split(/\s+/).filter(Boolean).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return esc.replace(new RegExp(`(${words.join('|')})`, 'gi'), '<mark>$1</mark>');
}

watch(query, (q) => {
  cursor.value = 0;
  clearTimeout(searchTimer);
  const term = q.trim();
  if (term.length < 1) {
    postHits.value = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    const seq = ++searchSeq;
    searching.value = true;
    try {
      const res = await adminFetch<{ items: Array<{ id: number; title: string; status: string; number: number | null }> }>('/api/v1/admin/posts', { query: { q: term, page_size: 6 } });
      if (seq !== searchSeq) return;
      postHits.value = (res.items || []).map((p) => ({
        id: `post-${p.id}`,
        group: '特稿',
        label: p.title,
        hint: `${p.status === 'published' ? '已发布' : '草稿'}${p.number ? ` · No.${String(p.number).padStart(3, '0')}` : ''}`,
        run: () => router.push(`/admin/posts/${p.id}`),
      }));
    } catch {
      if (seq === searchSeq) postHits.value = [];
    } finally {
      if (seq === searchSeq) searching.value = false;
    }
  }, 150);
});

watch(commands.open, (on) => {
  if (on) {
    query.value = '';
    cursor.value = 0;
    postHits.value = [];
    lockScroll();
    nextTick(() => inputRef.value?.focus());
  } else {
    unlockScroll();
  }
});

function close() {
  commands.toggle(false);
}
function run(c: AdminCommand | undefined) {
  if (!c) return;
  close();
  nextTick(() => c.run());
}
function onKeydown(e: KeyboardEvent) {
  const n = results.value.length;
  if (e.key === 'Escape') {
    e.preventDefault();
    close();
  } else if (e.key === 'ArrowDown' && n) {
    e.preventDefault();
    cursor.value = (cursor.value + 1) % n;
    scrollIntoView();
  } else if (e.key === 'ArrowUp' && n) {
    e.preventDefault();
    cursor.value = (cursor.value - 1 + n) % n;
    scrollIntoView();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    run(results.value[cursor.value]);
  }
}
function scrollIntoView() {
  nextTick(() => listRef.value?.querySelector<HTMLElement>('.cmd-item.is-cursor')?.scrollIntoView({ block: 'nearest' }));
}
</script>

<template>
  <Teleport to="body">
    <Transition name="cmd">
      <div v-if="commands.open.value" class="cmd-scrim" @mousedown.self="close">
        <div class="cmd" role="dialog" aria-modal="true" aria-label="检索与命令" @keydown="onKeydown">
          <div class="cmd-search">
            <Search :size="16" :stroke-width="1.5" class="cmd-search-icon" />
            <input
              ref="inputRef"
              v-model="query"
              class="cmd-input"
              type="text"
              placeholder="前往栏目、执行动作，或输入标题找特稿…"
              aria-label="检索"
              role="combobox"
              aria-expanded="true"
              aria-controls="cmd-list"
              :aria-activedescendant="results[cursor] ? `cmd-${results[cursor].id}` : undefined"
              autocomplete="off"
              spellcheck="false"
            >
            <span v-if="searching" class="a-spin" aria-hidden="true" />
            <kbd class="a-kbd">Esc</kbd>
          </div>

          <div id="cmd-list" ref="listRef" class="cmd-list" role="listbox" data-lenis-prevent>
            <template v-if="results.length">
              <div v-for="g in grouped" :key="g.group" class="cmd-group" role="group" :aria-label="g.group">
                <p class="cmd-group-label">{{ g.group }}</p>
                <button
                  v-for="c in g.items"
                  :id="`cmd-${c.id}`"
                  :key="c.id"
                  type="button"
                  role="option"
                  class="cmd-item"
                  :class="{ 'is-cursor': c.index === cursor }"
                  :aria-selected="c.index === cursor"
                  @mouseenter="cursor = c.index"
                  @click="run(c)"
                >
                  <FileText v-if="g.group === '特稿'" :size="14" :stroke-width="1.5" class="cmd-item-icon" />
                  <span v-else class="cmd-item-dot" aria-hidden="true" />
                  <!-- eslint-disable-next-line vue/no-v-html -->
                  <span class="cmd-item-label" v-html="highlight(c.label)" />
                  <span v-if="c.hint" class="cmd-item-hint">{{ c.hint }}</span>
                  <CornerDownLeft v-if="c.index === cursor" :size="13" :stroke-width="1.5" class="cmd-item-enter" />
                </button>
              </div>
            </template>
            <div v-else class="cmd-empty">
              <span class="cmd-empty-glyph" aria-hidden="true">∅</span>
              <p>{{ searching ? '正在翻找…' : `没有和「${query}」对得上的东西` }}</p>
            </div>
          </div>

          <footer class="cmd-foot">
            <span><kbd class="a-kbd">↑</kbd><kbd class="a-kbd">↓</kbd> 选择</span>
            <span><kbd class="a-kbd">↵</kbd> 执行</span>
            <span class="cmd-foot-right"><kbd class="a-kbd">g</kbd> + 字母 直接跳转</span>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.cmd-scrim {
  position: fixed;
  inset: 0;
  z-index: 1250;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: min(16vh, 140px) 16px 16px;
  background: color-mix(in oklab, var(--a-desk) 55%, transparent);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}
.cmd {
  width: min(620px, 100%);
  display: flex;
  flex-direction: column;
  max-height: min(560px, 76vh);
  overflow: hidden;
  background: var(--a-paper);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-float);
}
.cmd-search { display: flex; align-items: center; gap: 10px; height: 52px; padding: 0 14px; border-bottom: 1px solid var(--color-ink); }
.cmd-search-icon { color: var(--color-ink-muted); flex-shrink: 0; }
.cmd-input { flex: 1; min-width: 0; height: 100%; font-size: 15px; background: transparent; border: 0; outline: none; color: var(--color-ink); }
.cmd-list { flex: 1; overflow-y: auto; padding: 6px; }
.cmd-group + .cmd-group { margin-top: 6px; }
.cmd-group-label { padding: 8px 10px 4px; font-family: var(--font-serif); font-size: 11px; font-weight: 700; letter-spacing: 0.18em; color: var(--color-ink-faint); }
.cmd-item {
  position: relative;
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto 14px;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 10px;
  font-size: 13.5px;
  text-align: left;
  color: var(--color-ink-muted);
  border-radius: var(--a-radius-sm);
}
.cmd-item.is-cursor { color: var(--color-ink); background: var(--a-press); }
.cmd-item.is-cursor::before { content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 2px; background: var(--color-ink); }
.cmd-item-icon { color: var(--color-ink-faint); }
.cmd-item-dot { width: 5px; height: 5px; margin-left: 5px; background: var(--color-ink-faint); border-radius: 1px; }
.cmd-item.is-cursor .cmd-item-dot { background: var(--color-seal); }
.cmd-item-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cmd-item-label :deep(mark) { color: inherit; background: none; box-shadow: inset 0 -2px 0 var(--color-seal); }
.cmd-item-hint { font-family: var(--font-mono); font-size: 10.5px; color: var(--color-ink-faint); white-space: nowrap; }
.cmd-item-enter { color: var(--color-ink-muted); }
.cmd-empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 36px 16px; font-size: 13px; color: var(--color-ink-muted); }
.cmd-empty-glyph { font-family: var(--font-display); font-size: 36px; font-style: italic; font-weight: 300; color: var(--color-seal); }
.cmd-foot { display: flex; gap: 16px; padding: 9px 14px; font-size: 11.5px; color: var(--color-ink-faint); border-top: 1px solid var(--color-line); }
.cmd-foot span { display: inline-flex; align-items: center; gap: 4px; }
.cmd-foot-right { margin-left: auto; }
@media (max-width: 560px) { .cmd-foot-right { display: none; } }

.cmd-enter-active { transition: opacity var(--a-dur) ease; }
.cmd-enter-active .cmd { transition: transform var(--a-dur-md) var(--ease-out-expo), opacity var(--a-dur) ease; }
.cmd-leave-active { transition: opacity 120ms ease; }
.cmd-leave-active .cmd { transition: transform 120ms var(--ease-in-quart), opacity 120ms ease; }
.cmd-enter-from, .cmd-leave-to { opacity: 0; }
.cmd-enter-from .cmd { opacity: 0; transform: translate3d(0, -8px, 0) scale(0.985); }
.cmd-leave-to .cmd { opacity: 0; transform: scale(0.99); }
</style>
