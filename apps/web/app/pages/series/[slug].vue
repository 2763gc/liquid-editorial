<script setup lang="ts">
import { computed, ref, onMounted } from 'vue';

interface ChapterPost {
  id: number;
  slug: string;
  title: string;
  subtitle: string | null;
  excerpt: string | null;
  series_order: number | null;
  reading_minutes: number;
  published_at: string | null;
}

interface SeriesDetail {
  id: number;
  slug: string;
  title: string;
  description: string | null;
  status: string;
  post_count: number;
  total_words: number;
  total_reading_time: number;
  posts: ChapterPost[];
}

const route = useRoute();
const slug = route.params.slug as string;

const { data: series, error } = await useFetch<SeriesDetail>(`/api/v1/series/${slug}`);

if (error.value || !series.value) {
  throw createError({ statusCode: 404, statusMessage: '专栏未找到', fatal: true });
}

/** 目录页码：本章从整部专栏的第几分钟读起 */
const startMinute = computed(() => {
  let acc = 0;
  return (series.value?.posts || []).map((p) => {
    const at = acc;
    acc += p.reading_minutes || 0;
    return at;
  });
});

/** 读过的章节（本地记录，挂载后才读取，避免水合不一致） */
const readSet = ref<Set<string>>(new Set());
onMounted(() => {
  try { readSet.value = new Set(JSON.parse(localStorage.getItem(`blog_series_read_${slug}`) || '[]')); } catch {}
});
const readCount = computed(() => (series.value?.posts || []).filter((p) => readSet.value.has(p.slug)).length);

const stats = computed(() => {
  const s = series.value;
  if (!s) return [];
  return [
    { label: 'Chapters', value: s.post_count, unit: '章' },
    { label: 'Words', value: compactNumber(s.total_words), unit: '字' },
    { label: 'Reading', value: s.total_reading_time, unit: '分钟' },
  ];
});

useHead({
  title: computed(() => `${series.value?.title || '专栏'} · 专栏`),
  meta: [{ name: 'description', content: computed(() => series.value?.description || '') }],
});
</script>

<template>
  <div v-if="series" class="series-detail">
    <div class="page-shell series-back">
      <NuxtLink to="/series" class="back-link"><i aria-hidden="true">←</i> 全部专栏</NuxtLink>
    </div>

    <UiPageMasthead en="Series" :title="series.title" :lede="series.description || undefined" :stats="stats" size="md">
      <template #kicker>
        <span class="status-mark" :class="series.status === 'completed' ? 'is-done' : 'is-live'">{{ series.status === 'completed' ? '已完结' : '连载中' }}</span>
      </template>
    </UiPageMasthead>

    <div class="page-shell">
      <div class="section-rule chapters-head">
        <span class="section-rule-no">Chapters</span>
        <h2 class="section-rule-title">篇章目录</h2>
        <span class="section-rule-note">已读 {{ readCount }} / {{ series.post_count }}</span>
      </div>

      <ol v-if="series.posts.length" class="chapter-list" data-skew>
        <li v-for="(post, idx) in series.posts" :key="post.id" v-reveal="Math.min(idx, 8) * 50" class="reveal">
          <NuxtLink
            :to="`/posts/${post.slug}`"
            class="chapter-row register-focus"
            :class="{ 'is-read': readSet.has(post.slug) }"
            data-cursor="read"
          >
            <span class="chapter-no">
              <span class="chapter-check seal" :aria-label="readSet.has(post.slug) ? '已读' : undefined">✓</span>
              {{ String(post.series_order || idx + 1).padStart(2, '0') }}
            </span>
            <span class="chapter-main">
              <span class="chapter-title">{{ post.title }}</span>
              <span v-if="post.subtitle || post.excerpt" class="chapter-sub">{{ plainText(post.subtitle || post.excerpt, 90) }}</span>
            </span>
            <span class="leader" aria-hidden="true" />
            <span class="chapter-page" :title="`从第 ${startMinute[idx]} 分钟读起，约 ${post.reading_minutes} 分钟`">{{ startMinute[idx] }}′</span>
          </NuxtLink>
        </li>
      </ol>
      <div v-else class="empty-note">
        <span class="empty-note-glyph" aria-hidden="true">卷</span>
        <p class="empty-note-text">这一卷还在誊写，第一章很快就会装订进来。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.series-back { padding-top: clamp(28px, 3.5vw, 48px); }
.series-detail :deep(.masthead) { padding-top: clamp(32px, 5vw, 72px); }
.chapters-head { margin-top: clamp(40px, 5vw, 72px); border-bottom: 0; }
.chapter-list { list-style: none; border-top: 1px solid var(--color-ink); }
/* 目录页：章号 | 标题 ……引导点…… 页码（从第几分钟读起） */
.chapter-row {
  position: relative;
  display: grid;
  grid-template-columns: 88px auto minmax(32px, 1fr) 64px;
  align-items: baseline;
  column-gap: 14px;
  padding-block: 22px;
  border-bottom: 1px solid var(--color-line);
}
.chapter-no {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 28px;
  font-style: italic;
  font-weight: 300;
  line-height: 1;
  color: var(--color-ink-muted);
  font-variation-settings: "opsz" 72, "SOFT" 100;
}
.chapter-check { width: 20px; height: 20px; font-size: 11px; font-style: normal; border-width: 1.5px; opacity: 0; transform: scale(1.6) rotate(-12deg); transition: opacity 400ms var(--ease-out-quart), transform 500ms var(--ease-out-back); }
.chapter-row.is-read .chapter-check { opacity: 1; transform: rotate(-6deg); }
.chapter-main { display: flex; flex-direction: column; gap: 6px; min-width: 0; max-width: 34em; }
.chapter-title { font-family: var(--font-serif); font-size: clamp(19px, 1.8vw, 24px); font-weight: 700; line-height: 1.4; transition: transform 700ms var(--ease-out-expo); }
.chapter-row:hover .chapter-title { transform: translateX(8px); }
.chapter-row.is-read .chapter-title { color: var(--color-ink-muted); }
.chapter-sub { font-family: var(--font-serif); font-size: 14.5px; line-height: 1.7; color: var(--color-ink-muted); }
.chapter-page { font-family: var(--font-display); font-size: 20px; text-align: right; font-variant-numeric: tabular-nums; color: var(--color-ink-muted); }
.chapter-row:hover .chapter-page { color: var(--color-accent-text); }
@media (max-width: 760px) {
  .chapter-row { grid-template-columns: 64px 1fr; row-gap: 8px; }
  .chapter-row .leader { display: none; }
  .chapter-page { grid-column: 2; text-align: left; font-size: 14px; }
}
</style>
