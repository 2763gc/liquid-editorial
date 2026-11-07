<script setup lang="ts">
import { ref, computed } from 'vue';

const listRef = ref<HTMLElement | null>(null);
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

useHead({ title: "文章索引 · Luntrix's Editorial" });

const selectedTag = ref<string>((route.query.tag as string) || '');
const selectedYear = ref<string>((route.query.year as string) || '');

const { data: tags } = await useFetch<any[]>('/api/v1/tags', { default: () => [] });
const { data: years } = await useFetch<string[]>('/api/v1/archive', {
  key: 'post-years',
  transform: (d: any) => (d?.years || []).map((y: any) => String(y.year)),
  default: () => [],
});

const { data: postsData, pending } = await useFetch<any>('/api/v1/posts', {
  query: computed(() => ({
    tag: selectedTag.value || undefined,
    year: selectedYear.value || undefined,
    page_size: 50,
  })),
});

const items = computed<any[]>(() => postsData.value?.items || []);
const total = computed(() => postsData.value?.total ?? items.value.length);

const yearOptions = computed(() => [{ value: '', label: '全部年份' }, ...years.value.map((y) => ({ value: y, label: y }))]);

const stats = computed(() => {
  const words = items.value.reduce((s, p) => s + (p.word_count || 0), 0);
  const minutes = items.value.reduce((s, p) => s + (p.reading_minutes || 0), 0);
  return [
    { label: 'Issues', value: total.value, unit: '篇' },
    { label: 'Words', value: compactNumber(words), unit: '字' },
    { label: 'Reading', value: minutes, unit: '分钟' },
  ];
});

function setTag(slug: string) {
  selectedTag.value = selectedTag.value === slug ? '' : slug;
  syncQuery();
}
function setYear(year: string) {
  selectedYear.value = year;
  syncQuery();
}
function syncQuery() {
  router.replace({ query: { tag: selectedTag.value || undefined, year: selectedYear.value || undefined } });
}
</script>

<template>
  <div class="posts-page">
    <UiPageMasthead
      index="02"
      en="Table of Contents"
      label="特稿总目录"
      title="文章索引"
      lede="按期整理的深度长文、系统拆解与工程思考——关于系统架构、数字美学与开发者工具。"
      :stats="stats"
    />

    <div class="page-shell">
      <div v-reveal class="posts-filters reveal">
        <div class="filter-bar">
          <span class="filter-label">Tags</span>
          <div class="chip-set">
            <button type="button" class="chip" :class="{ 'is-active': !selectedTag }" @click="setTag('')">全部</button>
            <button
              v-for="t in tags"
              :key="t.slug"
              type="button"
              class="chip"
              :class="{ 'is-active': selectedTag === t.slug }"
              @click="setTag(t.slug)"
            >
              <span class="chip-dot" :style="{ color: t.color || 'var(--color-ink-faint)' }" aria-hidden="true" />{{ t.name }}
            </button>
          </div>
        </div>
        <div v-if="years.length" class="posts-years">
          <UiSegmented :model-value="selectedYear" :options="yearOptions" size="sm" aria-label="按年份筛选" @update:model-value="setYear" />
        </div>
      </div>

      <section ref="listRef" class="posts-list" :class="{ 'is-pending': pending }" aria-label="文章列表">
        <InkHoverPlate :scope="listRef" />
        <ol v-if="items.length" class="entry-list" data-skew>
          <li v-for="(post, i) in items" :key="post.slug" v-reveal="Math.min(i, 10) * 45" class="reveal">
            <NuxtLink
              :to="`/posts/${post.slug}`"
              class="entry-row register-focus"
              data-cursor="read"
              :data-plate="post.slug"
              :data-plate-no="post.number"
              :data-plate-accent="post.accent_color"
            >
              <span class="entry-no">No. {{ issueNo(post.number) }}<em v-if="post.is_pinned" class="entry-pin">置顶</em></span>
              <span class="entry-main">
                <span class="entry-title">{{ post.title }}</span>
                <span v-if="post.subtitle" class="entry-sub">{{ post.subtitle }}</span>
              </span>
              <span class="entry-tags">
                <span v-for="tag in (post.tags || []).slice(0, 2)" :key="tag.slug" class="editorial-tag">{{ tag.name }}</span>
              </span>
              <span class="entry-meta">
                <time :datetime="post.published_at">{{ dotDate(post.published_at) }}</time>
                <span>{{ post.reading_minutes }} 分钟</span>
              </span>
              <span class="entry-arrow" aria-hidden="true">→</span>
            </NuxtLink>
          </li>
        </ol>
        <div v-else class="empty-note">
          <span class="empty-note-glyph" aria-hidden="true">∅</span>
          <p class="empty-note-text">这一格还没有落墨。换一个标签或年份，或者回到全部特稿看看。</p>
          <p class="empty-note-meta">$ ls ./posts --tag={{ selectedTag || '*' }} --year={{ selectedYear || '*' }} → 0</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.posts-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px 40px;
  padding-block: 28px 40px;
}
.posts-filters .filter-bar { flex: 1 1 520px; align-items: baseline; }
.posts-filters .filter-label { padding-top: 6px; }
.posts-years { flex-shrink: 0; }
.posts-list { position: relative; transition: opacity var(--dur-sm) ease; }
.entry-no { display: inline-flex; flex-direction: column; align-items: flex-start; }
.posts-list.is-pending { opacity: 0.45; }
</style>
