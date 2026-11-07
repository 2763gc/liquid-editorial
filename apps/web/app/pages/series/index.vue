<script setup lang="ts">
import { computed, ref } from 'vue';

interface SeriesSummary {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  status: string;
  post_count: number;
  total_words: number;
}

const { data: seriesList } = await useFetch<SeriesSummary[]>('/api/v1/series', { default: () => [] });
const list = computed(() => seriesList.value || []);

/** 书脊：厚度按章节数，高度按总字数，在一个范围里错落 */
const books = computed(() => {
  const maxWords = Math.max(1, ...list.value.map((s) => s.total_words || 0));
  return list.value.map((s, i) => ({
    ...s,
    vol: String(i + 1).padStart(2, '0'),
    thick: Math.round(46 + Math.min(10, s.post_count || 1) * 9),
    tall: Math.round(300 + ((s.total_words || 0) / maxWords) * 120),
  }));
});
const pulled = ref<number | null>(null);

const stats = computed(() => [
  { label: 'Series', value: list.value.length, unit: '部' },
  { label: 'Chapters', value: list.value.reduce((s, x) => s + (x.post_count || 0), 0), unit: '章' },
  { label: 'Words', value: compactNumber(list.value.reduce((s, x) => s + (x.total_words || 0), 0)), unit: '字' },
]);

useHead({
  title: "专栏 · Luntrix's Editorial",
  meta: [{ name: 'description', content: '成体系的技术探索与工程深度特稿集合。' }],
});
</script>

<template>
  <div class="series-page">
    <UiPageMasthead
      index="03"
      en="Curated Series"
      label="专栏特辑"
      title="专栏"
      lede="系统化、多篇连载的技术长卷。从内核设计到工业级架构，按章节沉淀深度工程经验。"
      :stats="stats"
    />

    <div class="page-shell">
      <!-- 书架：每一部专栏是一本书 -->
      <div v-if="books.length" v-reveal class="shelf reveal" aria-hidden="true">
        <NuxtLink
          v-for="(b, i) in books"
          :key="b.id"
          :to="`/series/${b.slug}`"
          class="book"
          tabindex="-1"
          :class="{ 'is-pulled': pulled === i }"
          :style="{ '--thick': `${b.thick}px`, '--tall': `${b.tall}px`, '--i': i }"
          data-cursor="read"
          @mouseenter="pulled = i"
          @mouseleave="pulled = null"
        >
          <span class="book-art"><InkCover :seed="b.slug" variant="stroke" :width="120" :height="440" :numeral="false" :seal="false" bare /></span>
          <span class="book-vol">Vol.{{ b.vol }}</span>
          <span class="book-title">{{ b.title }}</span>
          <span class="book-seal seal">{{ b.status === 'completed' ? '完' : '续' }}</span>
          <span class="book-count">{{ b.post_count }} 章</span>
        </NuxtLink>
        <span class="shelf-board" />
      </div>

      <ol v-if="list.length" class="entry-list series-list" data-skew>
        <li v-for="(s, i) in list" :key="s.id" v-reveal="i * 60" class="reveal">
          <NuxtLink :to="`/series/${s.slug}`" class="entry-row series-row register-focus" data-cursor="read" @mouseenter="pulled = i" @mouseleave="pulled = null">
            <span class="series-no font-display">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="entry-main">
              <span class="entry-title series-title">{{ s.title }}</span>
              <span class="entry-sub">{{ s.description || '暂无专栏描述' }}</span>
            </span>
            <span class="status-mark" :class="s.status === 'completed' ? 'is-done' : 'is-live'">{{ s.status === 'completed' ? '已完结' : '连载中' }}</span>
            <span class="entry-meta">
              <span>{{ s.post_count }} 章</span>
              <span>{{ compactNumber(s.total_words) }} 字</span>
            </span>
            <span class="entry-arrow" aria-hidden="true">→</span>
          </NuxtLink>
        </li>
      </ol>
      <div v-else class="empty-note">
        <span class="empty-note-glyph" aria-hidden="true">卷</span>
        <p class="empty-note-text">书架还空着。第一部专栏正在装订，过些日子再来翻翻。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---------------- 书架 ---------------- */
.shelf {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 6px;
  min-height: 480px;
  padding: 56px clamp(8px, 3vw, 48px) 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.shelf::-webkit-scrollbar { display: none; }
.shelf-board {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 14px;
  border-top: 1px solid var(--color-ink);
  background: linear-gradient(var(--color-surface), var(--color-surface-2));
  box-shadow: 0 18px 30px -24px rgb(var(--shadow-rgb) / calc(0.5 * var(--shadow-k)));
}
.book {
  position: relative;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  width: var(--thick);
  height: var(--tall);
  margin-bottom: 14px;
  padding: 16px 0 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-line-strong);
  border-radius: 2px 2px 0 0;
  overflow: hidden;
  box-shadow: inset -6px 0 10px -8px rgb(var(--shadow-rgb) / calc(0.35 * var(--shadow-k))), inset 4px 0 0 -2px color-mix(in oklab, var(--color-bg) 60%, transparent);
  transform-origin: 50% 100%;
  transition: transform 700ms var(--ease-spring), box-shadow 700ms var(--ease-out-expo);
}
.book:nth-child(3n + 2) { background: var(--color-surface-2); }
.book:nth-child(4n + 3) { transform: rotate(-1.4deg); }
/* 抽书：从书架上抽出一截，像被手指勾住 */
.book.is-pulled {
  transform: translate3d(0, -26px, 0) rotate(0deg);
  box-shadow: inset -6px 0 10px -8px rgb(var(--shadow-rgb) / calc(0.35 * var(--shadow-k))), 0 24px 40px -24px rgb(var(--shadow-rgb) / calc(0.5 * var(--shadow-k)));
}
.book-art { position: absolute; inset: 0; opacity: 0.4; transition: opacity 700ms var(--ease-out-quart); }
.book.is-pulled .book-art { opacity: 0.75; }
.book > :not(.book-art) { position: relative; }
.book-vol { font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.1em; color: var(--color-ink-muted); writing-mode: vertical-rl; }
.book-title {
  flex: 1;
  writing-mode: vertical-rl;
  font-family: var(--font-serif);
  font-size: clamp(17px, 1.4vw, 21px);
  font-weight: 900;
  letter-spacing: 0.18em;
  line-height: 1.2;
  overflow: hidden;
}
.book-seal { width: 24px; height: 24px; font-size: 12px; border-width: 1.5px; }
.book-count { font-family: var(--font-mono); font-size: 9.5px; color: var(--color-ink-muted); writing-mode: vertical-rl; }
html.motion-ready .shelf.is-in .book { animation: book-in 900ms var(--ease-out-expo) backwards; animation-delay: calc(var(--i) * 60ms); }
@keyframes book-in { from { transform: translate3d(0, 40px, 0); opacity: 0; } }

/* 刊头的墨线即列表的上沿，不再重复画线 */
.series-list { border-top: 1px solid var(--color-ink); margin-top: 56px; }
.series-row { padding-block: clamp(28px, 3vw, 40px); align-items: center; }
.series-no {
  align-self: start;
  font-size: clamp(44px, 4.6vw, 68px);
  font-style: italic;
  font-weight: 300;
  line-height: 0.85;
  letter-spacing: -0.05em;
  color: var(--color-ink-faint);
  font-variation-settings: "opsz" 144, "SOFT" 100, "WONK" 1;
  transition: color var(--dur-sm) ease;
}
.series-row:hover .series-no { color: var(--color-accent-text); }
.series-title { font-size: clamp(22px, 2.4vw, 34px); font-weight: 900; letter-spacing: -0.015em; }
.series-row .entry-sub { max-width: 40em; }
.series-row .status-mark { justify-self: end; }
@media (max-width: 760px) {
  .series-row .status-mark { grid-column: 2; justify-self: start; }
}
</style>
