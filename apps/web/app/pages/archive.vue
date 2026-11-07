<script setup lang="ts">
import { computed } from 'vue';

useHead({ title: "时间河流 · Luntrix's Editorial" });

const { data: archiveData } = await useFetch<any>('/api/v1/archive');

const MONTHS = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];

/** 年 → 月 → 文章，月份按时间倒序 */
const years = computed(() =>
  (archiveData.value?.years || []).map((y: any) => {
    const months = new Map<string, any[]>();
    for (const p of y.posts || []) {
      const m = p.month || p.date?.slice(5, 7) || '01';
      if (!months.has(m)) months.set(m, []);
      months.get(m)!.push(p);
    }
    return {
      year: String(y.year),
      count: y.count,
      words: (y.posts || []).reduce((s: number, p: any) => s + (p.word_count || 0), 0),
      months: [...months.entries()]
        .sort((a, b) => Number(b[0]) - Number(a[0]))
        .map(([m, posts]) => ({ key: m, label: MONTHS[Number(m) - 1] || m, posts })),
    };
  }),
);

const LAYOUT: Record<string, string> = { standard: '标准', wide: '宽幅', immersive: '沉浸', essay: '随笔', showcase: '作品' };

const stats = computed(() => {
  const s = archiveData.value?.stats || {};
  return [
    { label: 'Issues', value: s.total_posts || 0, unit: '篇' },
    { label: 'Words', value: compactNumber(s.total_words), unit: '字' },
    { label: 'Span', value: s.years_span || 1, unit: '年' },
  ];
});
</script>

<template>
  <div class="archive-page">
    <UiPageMasthead
      index="06"
      en="Time Stream"
      label="时间河流归档"
      title="时间河流"
      lede="按时间倒序排列的全部特稿。每一篇都是某个阶段的切片，连起来便是一条创作的河流。"
      :stats="stats"
    />

    <div class="page-shell">
      <section v-for="y in years" :key="y.year" class="year-block" :aria-labelledby="`y-${y.year}`">
        <aside class="year-aside">
          <div class="year-sticky">
            <h2 :id="`y-${y.year}`" class="year-num font-display">{{ y.year }}</h2>
            <p class="year-meta">{{ y.count }} 篇 · {{ compactNumber(y.words) }} 字</p>
          </div>
        </aside>

        <div class="year-body">
          <div v-for="m in y.months" :key="m.key" class="month">
            <h3 class="month-head">
              <span class="month-no">{{ m.key }}</span>
              <span class="month-label">{{ m.label }}</span>
              <span class="month-count">{{ m.posts.length }}</span>
            </h3>
            <ol class="month-list">
              <li v-for="(post, i) in m.posts" :key="post.slug" v-reveal="Math.min(i, 8) * 40" class="reveal">
                <NuxtLink :to="`/posts/${post.slug}`" class="arc-row" data-cursor="read">
                  <time class="arc-day">{{ post.date?.slice(8, 10) }}</time>
                  <span class="arc-title">{{ post.title }}</span>
                  <span class="arc-leader" aria-hidden="true" />
                  <span class="arc-meta">{{ LAYOUT[post.layout_variant] || post.layout_variant }} · {{ post.word_count?.toLocaleString() }} 字</span>
                  <span class="arc-no">No. {{ issueNo(post.number) }}</span>
                </NuxtLink>
              </li>
            </ol>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.year-block {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(0, 3fr);
  gap: clamp(24px, 4vw, 72px);
  padding-top: clamp(40px, 5vw, 72px);
}
.year-block + .year-block { margin-top: clamp(32px, 4vw, 56px); border-top: 1px solid var(--color-line); }

.year-sticky {
  position: sticky;
  top: calc(var(--header-h) + 32px);
}
.year-num {
  font-size: clamp(64px, 8vw, 128px);
  font-weight: 300;
  font-style: italic;
  line-height: 0.85;
  letter-spacing: -0.05em;
  color: var(--color-ink);
  font-variation-settings: "opsz" 144, "SOFT" 100, "WONK" 1;
}
.year-meta {
  margin-top: 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--color-ink-muted);
}

.month + .month { margin-top: 48px; }
.month-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-ink);
  font-size: inherit;
  font-weight: inherit;
  line-height: 1;
}
.month-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; color: var(--color-accent); }
.month-label { font-family: var(--font-serif); font-size: 15px; font-weight: 700; }
.month-count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-faint);
}

.month-list { list-style: none; }
.arc-row {
  position: relative;
  display: grid;
  grid-template-columns: 36px minmax(0, max-content) minmax(24px, 1fr) auto 72px;
  align-items: baseline;
  gap: 16px;
  padding-block: 18px;
  border-bottom: 1px solid var(--color-line);
}
.arc-row::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 1px;
  background: var(--color-ink);
  transform: scaleX(0);
  transform-origin: 100% 50%;
  transition: transform 800ms var(--ease-out-expo);
}
.arc-row:hover::after { transform: scaleX(1); transform-origin: 0 50%; }
.arc-day {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 400;
  line-height: 1;
  color: var(--color-ink-faint);
  font-variant-numeric: tabular-nums lining-nums;
  transition: color var(--dur-sm) ease;
}
.arc-row:hover .arc-day { color: var(--color-accent); }
.arc-title {
  font-family: var(--font-serif);
  font-size: clamp(16.5px, 1.4vw, 19px);
  font-weight: 700;
  line-height: 1.5;
  transition: transform 700ms var(--ease-out-expo);
}
.arc-row:hover .arc-title { transform: translateX(6px); }
/* 目录式引导点线 */
.arc-leader {
  align-self: center;
  height: 1px;
  background-image: radial-gradient(circle, var(--color-line-strong) 0.8px, transparent 1px);
  background-size: 6px 2px;
  background-repeat: repeat-x;
  background-position: 0 50%;
  opacity: 0.8;
}
.arc-meta, .arc-no {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-muted);
  white-space: nowrap;
}
.arc-no { text-align: right; color: var(--color-ink-faint); }

@media (max-width: 860px) {
  .year-block { grid-template-columns: 1fr; gap: 24px; }
  .year-sticky { position: static; display: flex; align-items: baseline; gap: 16px; }
  .year-meta { margin-top: 0; }
  .arc-row { grid-template-columns: 32px minmax(0, 1fr); row-gap: 6px; }
  .arc-leader, .arc-no { display: none; }
  .arc-meta { grid-column: 2; }
}
</style>
