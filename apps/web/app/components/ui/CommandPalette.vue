<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useTheme } from '~/composables/useTheme';
import { lockScroll, unlockScroll } from '~/composables/useLenis';

interface Hit { type: string; slug: string; title: string; snippet: string; url: string; number?: number }
interface Command { id: string; label: string; hint: string; run: () => void }

const router = useRouter();
const theme = useTheme();

const isOpen = ref(false);
const query = ref('');
const results = ref<Hit[]>([]);
const activeIndex = ref(0);
const isSearching = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);
const listRef = ref<HTMLElement | null>(null);
const isMac = ref(true);

const RECENT_KEY = 'blog_recent_search';
const recent = ref<string[]>([]);

const commands: Command[] = [
  { id: 'theme', label: '切换主题（自动 / 昼 / 夜）', hint: 'T', run: () => theme.cycle() },
  { id: 'posts', label: '前往 · 文章索引', hint: '/posts', run: () => go('/posts') },
  { id: 'series', label: '前往 · 专栏', hint: '/series', run: () => go('/series') },
  { id: 'projects', label: '前往 · 开源项目', hint: '/projects', run: () => go('/projects') },
  { id: 'til', label: '前往 · 今日所学', hint: '/til', run: () => go('/til') },
  { id: 'archive', label: '前往 · 归档', hint: '/archive', run: () => go('/archive') },
  { id: 'about', label: '前往 · 关于', hint: '/about', run: () => go('/about') },
  { id: 'copy', label: '复制当前页面链接', hint: '⧉', run: () => navigator.clipboard?.writeText(location.href) },
  { id: 'rss', label: '打开 RSS 订阅源', hint: 'RSS', run: () => window.open('/rss.xml', '_blank', 'noopener') },
];

const mode = computed<'commands' | 'search' | 'empty'>(() => {
  const q = query.value.trim();
  if (!q || q.startsWith('>')) return 'commands';
  return 'search';
});

const visibleCommands = computed(() => {
  const q = query.value.replace(/^>\s*/, '').trim().toLowerCase();
  if (!q) return commands;
  return commands.filter((c) => c.label.toLowerCase().includes(q) || c.hint.toLowerCase().includes(q));
});

const itemCount = computed(() => (mode.value === 'commands' ? visibleCommands.value.length : results.value.length));

function go(path: string) {
  router.push(path);
}

async function open() {
  if (isOpen.value) return;
  isOpen.value = true;
  query.value = '';
  results.value = [];
  activeIndex.value = 0;
  lockScroll();
  await nextTick();
  inputRef.value?.focus();
}

function close() {
  if (!isOpen.value) return;
  isOpen.value = false;
  unlockScroll();
}

let timer: ReturnType<typeof setTimeout> | null = null;
let seq = 0;
watch(query, (val) => {
  activeIndex.value = 0;
  if (timer) clearTimeout(timer);
  const q = val.trim();
  if (!q || q.startsWith('>')) {
    results.value = [];
    isSearching.value = false;
    return;
  }
  isSearching.value = true;
  timer = setTimeout(async () => {
    const id = ++seq;
    try {
      const data = await $fetch<{ results: Hit[] }>('/api/v1/search', { query: { q, limit: 12 } });
      if (id === seq) results.value = data.results || [];
    } catch {
      if (id === seq) results.value = [];
    } finally {
      if (id === seq) isSearching.value = false;
    }
  }, 150);
});

function remember(q: string) {
  const list = [q, ...recent.value.filter((x) => x !== q)].slice(0, 5);
  recent.value = list;
  try { localStorage.setItem(RECENT_KEY, JSON.stringify(list)); } catch {}
}

function execute(index = activeIndex.value) {
  if (mode.value === 'commands') {
    const cmd = visibleCommands.value[index];
    if (!cmd) return;
    close();
    cmd.run();
    return;
  }
  const hit = results.value[index];
  if (!hit) return;
  remember(query.value.trim());
  close();
  router.push(hit.url);
}

function scrollActiveIntoView() {
  nextTick(() => {
    listRef.value?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
  });
}

/* ---- 选中高亮：一块底色在条目之间滑动，键盘与鼠标共用 ---- */
const hl = ref({ y: 0, h: 0, on: false });
const hlReady = ref(false);
function placeHighlight() {
  const el = listRef.value?.querySelector<HTMLElement>('[data-active="true"]');
  hl.value = el ? { y: el.offsetTop, h: el.offsetHeight, on: true } : { ...hl.value, on: false };
}
watch([activeIndex, mode, () => results.value.length, () => visibleCommands.value.length, isOpen], () => nextTick(placeHighlight));
watch(isOpen, (v) => {
  hlReady.value = false;
  if (v) nextTick(() => requestAnimationFrame(() => { hlReady.value = true; }));
});

function onKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  const typing = !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    isOpen.value ? close() : open();
    return;
  }
  if (!isOpen.value) {
    if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      open();
    }
    return;
  }
  if (e.key === 'Escape') {
    e.preventDefault();
    close();
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (itemCount.value) activeIndex.value = (activeIndex.value + 1) % itemCount.value;
    scrollActiveIntoView();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (itemCount.value) activeIndex.value = (activeIndex.value - 1 + itemCount.value) % itemCount.value;
    scrollActiveIntoView();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (mode.value === 'search' && !results.value.length && query.value.trim()) {
      const q = query.value.trim();
      remember(q);
      close();
      router.push({ path: '/search', query: { q } });
      return;
    }
    execute();
  }
}

/** 把命中的关键词包上 <mark>（先转义再高亮，避免 XSS） */
function highlight(text: string): string {
  const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
  const safe = esc(text || '');
  const terms = query.value.trim().split(/\s+/).filter((w) => w.length > 0).map((w) => esc(w).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!terms.length) return safe;
  return safe.replace(new RegExp(`(${terms.join('|')})`, 'gi'), '<mark>$1</mark>');
}

onMounted(() => {
  isMac.value = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  try { recent.value = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]'); } catch {}
  window.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  if (isOpen.value) unlockScroll();
});

defineExpose({ open, close });
</script>

<template>
  <button type="button" class="palette-trigger" aria-label="搜索与命令面板" @click="open">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
    <span class="palette-trigger-text">搜索</span>
    <kbd class="palette-trigger-kbd">{{ isMac ? '⌘' : 'Ctrl' }} K</kbd>
  </button>

  <Teleport to="body">
    <Transition name="palette">
      <div v-if="isOpen" class="palette-backdrop" @mousedown.self="close">
        <div class="palette" role="dialog" aria-modal="true" aria-label="搜索与命令面板">
          <div class="palette-input-row">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
            <input
              ref="inputRef"
              v-model="query"
              type="text"
              class="palette-input"
              placeholder="搜索文章、代码标识符，输入 > 执行命令"
              autocomplete="off"
              spellcheck="false"
              aria-label="搜索"
            >
            <span v-if="isSearching" class="palette-spinner" aria-label="搜索中" />
            <kbd>Esc</kbd>
          </div>

          <div ref="listRef" class="palette-list" :class="{ 'is-ready': hlReady }" data-lenis-prevent>
            <span
              class="palette-hl"
              :class="{ 'is-on': hl.on }"
              :style="{ transform: `translate3d(0, ${hl.y}px, 0)`, height: `${hl.h}px` }"
              aria-hidden="true"
            />
            <template v-if="mode === 'commands'">
              <div v-if="!query && recent.length" class="palette-group">
                <p class="palette-group-title">最近搜索</p>
                <div class="palette-recent">
                  <button v-for="r in recent" :key="r" type="button" class="editorial-tag" @click="query = r">{{ r }}</button>
                </div>
              </div>
              <div class="palette-group">
                <p class="palette-group-title">命令</p>
                <button
                  v-for="(cmd, idx) in visibleCommands"
                  :key="cmd.id"
                  type="button"
                  class="palette-item"
                  :data-active="activeIndex === idx"
                  @mousemove="activeIndex = idx"
                  @click="execute(idx)"
                >
                  <span class="palette-item-title">{{ cmd.label }}</span>
                  <span class="palette-item-hint">{{ cmd.hint }}</span>
                </button>
                <p v-if="!visibleCommands.length" class="palette-empty">没有匹配的命令</p>
              </div>
            </template>

            <template v-else>
              <div v-if="results.length" class="palette-group">
                <p class="palette-group-title">文章 · {{ results.length }} 条结果</p>
                <button
                  v-for="(hit, idx) in results"
                  :key="hit.url"
                  type="button"
                  class="palette-item is-hit"
                  :data-active="activeIndex === idx"
                  @mousemove="activeIndex = idx"
                  @click="execute(idx)"
                >
                  <span class="palette-hit-no">No.{{ String(hit.number || 0).padStart(3, '0') }}</span>
                  <span class="palette-hit-body">
                    <span class="palette-item-title" v-html="highlight(hit.title)" />
                    <span class="palette-hit-snippet" v-html="highlight(hit.snippet)" />
                  </span>
                </button>
              </div>
              <p v-else-if="!isSearching" class="palette-empty">没有找到与「{{ query }}」相关的内容，按回车查看完整搜索页</p>
            </template>
          </div>

          <div class="palette-foot">
            <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
            <span><kbd>↵</kbd> 打开</span>
            <span><kbd>&gt;</kbd> 命令模式</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.palette-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 8px 0 12px;
  border-radius: 999px;
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
  background: color-mix(in oklab, var(--color-ink) 4%, transparent);
  transition: color var(--dur-micro) ease, background-color var(--dur-micro) ease;
}
.palette-trigger:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 8%, transparent); }
.palette-trigger-kbd { font-size: 10px; }
@media (max-width: 640px) {
  .palette-trigger-text, .palette-trigger-kbd { display: none; }
  .palette-trigger { padding: 0 11px; }
}

.palette-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-palette);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 14vh 16px 16px;
  background: color-mix(in oklab, var(--color-bg) 55%, transparent);
  -webkit-backdrop-filter: blur(10px) saturate(1.2);
  backdrop-filter: blur(10px) saturate(1.2);
}
.palette {
  width: 100%;
  max-width: 640px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  background: color-mix(in oklab, var(--color-bg) 94%, transparent);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-float), var(--edge-light);
  -webkit-backdrop-filter: blur(24px) saturate(1.6);
  backdrop-filter: blur(24px) saturate(1.6);
  overflow: hidden;
}
.palette-input-row {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 60px;
  padding: 0 18px;
  border-bottom: 1px solid var(--color-line);
  color: var(--color-ink-muted);
}
.palette-input {
  flex: 1;
  height: 100%;
  background: transparent;
  border: 0;
  outline: 0;
  font-size: 1rem;
  color: var(--color-ink);
}
.palette-input::placeholder { color: var(--color-ink-faint); }
.palette-spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid var(--color-line-strong);
  border-top-color: var(--color-accent);
  animation: spin 700ms linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.palette-list { position: relative; flex: 1; overflow-y: auto; padding: 8px; overscroll-behavior: contain; isolation: isolate; }
.palette-hl {
  position: absolute;
  top: 0;
  left: 8px;
  right: 8px;
  z-index: -1;
  border-radius: var(--radius-md);
  background: color-mix(in oklab, var(--color-ink) 6%, transparent);
  box-shadow: inset 2px 0 0 var(--color-accent);
  opacity: 0;
  pointer-events: none;
}
.palette-hl.is-on { opacity: 1; }
.palette-list.is-ready .palette-hl {
  transition: transform 420ms var(--ease-spring), height 420ms var(--ease-spring), opacity 200ms ease;
}
.palette-group + .palette-group { margin-top: 8px; }
.palette-group-title {
  padding: 8px 10px 6px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-ink-faint);
}
.palette-recent { display: flex; flex-wrap: wrap; gap: 6px; padding: 0 10px 6px; }
.palette-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  min-height: 42px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  text-align: left;
  font-size: var(--fs-small);
  color: var(--color-ink-muted);
  transition: color 200ms ease;
}
.palette-item[data-active="true"] { color: var(--color-ink); }
.palette-item-title { flex: 1; font-weight: 500; transition: transform 400ms var(--ease-out-expo); }
.palette-item[data-active="true"] .palette-item-title { transform: translateX(3px); }
.palette-item-hint { font-family: var(--font-mono); font-size: 11px; color: var(--color-ink-faint); }
.palette-item.is-hit { align-items: flex-start; }
.palette-hit-no { padding-top: 2px; font-family: var(--font-mono); font-size: 11px; color: var(--color-accent); flex-shrink: 0; }
.palette-hit-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.palette-hit-snippet {
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.palette-item :deep(mark) { background: color-mix(in oklab, var(--color-accent) 18%, transparent); color: inherit; border-radius: 2px; padding: 0 1px; }
.palette-empty { padding: 32px 12px; text-align: center; font-size: var(--fs-small); color: var(--color-ink-muted); }
.palette-foot {
  display: flex;
  gap: 18px;
  padding: 10px 18px;
  border-top: 1px solid var(--color-line);
  font-size: 11px;
  color: var(--color-ink-faint);
}
.palette-foot kbd { margin-right: 4px; }

.palette-enter-active { transition: opacity 260ms var(--ease-out-quart); }
.palette-enter-active .palette { transition: transform 520ms var(--ease-spring), opacity 260ms ease, filter 360ms ease; }
.palette-leave-active { transition: opacity 180ms ease; }
.palette-leave-active .palette { transition: transform 180ms var(--ease-in-quart), opacity 180ms ease; }
.palette-enter-from, .palette-leave-to { opacity: 0; }
.palette-enter-from .palette { transform: translateY(-10px) scale(0.965); opacity: 0; filter: blur(4px); }
.palette-leave-to .palette { transform: scale(0.98); opacity: 0; }
</style>
