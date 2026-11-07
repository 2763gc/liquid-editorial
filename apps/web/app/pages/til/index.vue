<script setup lang="ts">
import { ref, computed } from 'vue';
import { useTypewriter } from '~/composables/motion/useTypewriter';

const feedRef = ref<HTMLElement | null>(null);
useTypewriter(feedRef);

interface TILItem {
  id: number;
  title: string;
  tag: string;
  content_md: string;
  created_at: string;
}

interface TagCount {
  tag: string;
  count: number;
}

const activeTag = ref<string | null>(null);
const page = ref(1);
const copiedId = ref<number | null>(null);

const { data: tagsData } = await useFetch<TagCount[]>('/api/v1/til/tags', { default: () => [] });
const tags = computed(() => tagsData.value || []);

const { data: tilData, pending } = await useFetch<{
  items: TILItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}>(() => {
  const query = new URLSearchParams({ page: page.value.toString() });
  if (activeTag.value) query.append('tag', activeTag.value);
  return `/api/v1/til?${query.toString()}`;
});

const items = computed(() => tilData.value?.items || []);
const totalAll = computed(() => tags.value.reduce((s, t) => s + t.count, 0));

function selectTag(t: string | null) {
  activeTag.value = t;
  page.value = 1;
}

async function copyTil(item: TILItem) {
  try {
    await navigator.clipboard.writeText(`${item.title}\n\n${item.content_md}`);
    copiedId.value = item.id;
    setTimeout(() => { copiedId.value = null; }, 1800);
  } catch {}
}

/** TIL 正文的轻量渲染：整体转义后只还原代码块、行内代码与粗体，杜绝 XSS */
function renderLite(md: string) {
  const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
  const blocks: string[] = [];
  const text = esc((md || '').replace(/\\n/g, '\n')).replace(/```([a-z0-9+-]*)\n?([\s\S]*?)```/gi, (_m, lang, code) => {
    blocks.push(`<pre data-lang="${lang || 'code'}"><code>${code.replace(/\n$/, '')}</code></pre>`);
    return `\n\n\u0000${blocks.length - 1}\u0000\n\n`;
  });
  return text
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => (/^\u0000\d+\u0000$/.test(p) ? blocks[Number(p.slice(1, -1))] : `<p>${p.replace(/\n/g, '<br>')}</p>`))
    .join('');
}

useHead({
  title: "Today I Learned · Luntrix's Editorial",
  meta: [{ name: 'description', content: '开发者每日代码片段、系统底层思考与踩坑经验的即时记录。' }],
});
</script>

<template>
  <div class="til-page">
    <UiPageMasthead
      index="05"
      en="Today I Learned"
      label="今日所学"
      title="知识切片"
      lede="代码片段、底层原理、工具技巧与即时思考的原子化沉淀。短小，但每一条都经过验证。"
      :stats="[{ label: 'Entries', value: totalAll, unit: '条' }, { label: 'Topics', value: tags.length, unit: '类' }]"
    >
      <div class="filter-bar">
        <span class="filter-label">grep --tag</span>
        <div class="chip-set">
          <button type="button" class="chip" :class="{ 'is-active': activeTag === null }" @click="selectTag(null)">all<span class="chip-count">{{ totalAll }}</span></button>
          <button
            v-for="t in tags"
            :key="t.tag"
            type="button"
            class="chip til-chip"
            :class="{ 'is-active': activeTag === t.tag }"
            @click="selectTag(t.tag)"
          >#{{ t.tag }}<span class="chip-count">{{ t.count }}</span></button>
        </div>
      </div>
    </UiPageMasthead>

    <div class="page-shell">
      <ol v-if="items.length" ref="feedRef" class="til-feed" :class="{ 'is-pending': pending }">
        <li v-for="(item, i) in items" :key="item.id" v-reveal="Math.min(i, 6) * 60" class="til-entry reveal" :class="{ 'is-latest': i === 0 && page === 1 }" data-type-entry>
          <div class="til-gutter">
            <time class="til-date" :datetime="item.created_at">{{ dotDate(item.created_at) }}</time>
            <span class="til-tag">#{{ item.tag }}</span>
          </div>
          <article class="til-card">
            <header class="til-cmd">
              <span class="til-prompt">$</span>
              <span class="til-cmd-text" :data-type="`til show ${String(item.id).padStart(4, '0')} --tag ${item.tag}`" :data-type-id="`til-${item.id}`">til show {{ String(item.id).padStart(4, '0') }} --tag {{ item.tag }}</span><span class="til-caret" aria-hidden="true" />
              <button type="button" class="til-copy" :class="{ 'is-copied': copiedId === item.id }" @click="copyTil(item)">
                {{ copiedId === item.id ? '已复制' : '复制' }}
              </button>
            </header>
            <h2 class="til-title">{{ item.title }}</h2>
            <div class="til-body" v-html="renderLite(item.content_md)" />
          </article>
        </li>
      </ol>
      <div v-else class="empty-note">
        <span class="empty-note-glyph" aria-hidden="true">$_</span>
        <p class="empty-note-text">这个标签下还没有切片。终端开着，光标在等下一条。</p>
        <p class="empty-note-meta">$ til --find {{ activeTag || '*' }} → 0</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.til-chip { font-family: var(--font-mono); font-size: 11.5px; }

.til-feed {
  list-style: none;
  transition: opacity var(--dur-sm) ease;
}
.til-feed.is-pending { opacity: 0.45; }
.til-entry {
  display: grid;
  grid-template-columns: 140px minmax(0, 1fr);
  gap: clamp(20px, 3vw, 48px);
  padding-block: 32px;
}
.til-entry + .til-entry { border-top: 1px solid var(--color-line); }
.til-gutter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 14px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-ink-muted);
}
.til-tag { color: var(--color-accent); }

.til-card {
  max-width: 760px;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  box-shadow: var(--edge-light);
  overflow: hidden;
  transition: border-color var(--dur-sm) ease, box-shadow 600ms var(--ease-out-quart), transform 700ms var(--ease-out-expo);
}
.til-card:hover { border-color: var(--color-line-strong); box-shadow: var(--shadow-md), var(--edge-light); transform: translateY(-2px); }
.til-cmd {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 8px 0 16px;
  border-bottom: 1px solid var(--color-line);
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-ink-muted);
}
.til-prompt { color: var(--color-accent); font-weight: 600; }
.til-cmd-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.til-cmd-text em { font-style: normal; color: var(--color-ink-faint); }
.til-copy {
  height: 26px;
  padding: 0 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-muted);
  border-radius: var(--radius-xs);
  opacity: 0;
  transition: opacity var(--dur-micro) ease, color var(--dur-micro) ease, background-color var(--dur-micro) ease;
}
.til-card:hover .til-copy, .til-copy:focus-visible, .til-copy.is-copied { opacity: 1; }
.til-copy:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 6%, transparent); }
.til-copy.is-copied { color: var(--color-accent); }
@media (hover: none) { .til-copy { opacity: 1; } }

.til-title {
  padding: 22px 24px 0;
  font-family: var(--font-serif);
  font-size: clamp(18px, 1.7vw, 22px);
  font-weight: 700;
  line-height: 1.45;
}
.til-body {
  padding: 10px 24px 24px;
  font-family: var(--font-serif);
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  overflow-wrap: anywhere;
}
.til-body :deep(* + *) { margin-top: 0.8em; }
.til-body :deep(pre) {
  position: relative;
  padding: 14px 16px;
  overflow-x: auto;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--color-ink);
  background: var(--color-code-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
}
.til-body :deep(pre)::before {
  content: attr(data-lang);
  position: absolute;
  top: 8px;
  right: 10px;
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-ink-faint);
}
.til-body :deep(pre code) { padding: 0; font-size: inherit; background: none; }
.til-body :deep(code) {
  padding: 0.12em 0.38em;
  font-size: 0.86em;
  color: var(--color-ink);
  background: color-mix(in oklab, var(--color-ink) 6%, transparent);
  border-radius: 3px;
}
.til-body :deep(strong) { color: var(--color-ink); }

@media (max-width: 760px) {
  .til-entry { grid-template-columns: 1fr; gap: 10px; }
  .til-gutter { flex-direction: row; gap: 12px; padding-top: 0; }
}

/* ---------------- 终端打字（v2） ---------------- */
.til-caret {
  display: none;
  width: 0.55em;
  height: 1.05em;
  margin-left: 2px;
  vertical-align: -0.18em;
  background: var(--color-accent);
}
.til-entry.is-typing .til-caret,
.til-entry.is-latest.is-typed .til-caret,
.til-entry.is-latest:not(.is-typing) .til-caret { display: inline-block; animation: caret 1.05s steps(1) infinite; }
html.reduce-motion .til-caret { animation: none !important; }
/* 命令敲完、回车之后，结果才出现 */
.til-entry.is-typing .til-title,
.til-entry.is-typing .til-body { opacity: 0; transform: translate3d(0, 8px, 0); }
.til-entry .til-title,
.til-entry .til-body { transition: opacity 500ms var(--ease-out-quart), transform 700ms var(--ease-out-expo); }
.til-entry.is-typed .til-body { transition-delay: 80ms; }
</style>
