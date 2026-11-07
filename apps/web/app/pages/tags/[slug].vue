<script setup lang="ts">
import { computed } from 'vue';

const route = useRoute();
const slug = computed(() => String(route.params.slug || ''));

const { data, error } = await useFetch<any>(() => `/api/v1/tags/${encodeURIComponent(slug.value)}`);

if (error.value || !data.value) {
  throw createError({ statusCode: 404, statusMessage: '标签不存在', fatal: true });
}

useHead({ title: computed(() => `#${data.value?.tag?.name || ''} · Luntrix's Editorial`) });

const stats = computed(() => {
  const posts: any[] = data.value?.posts || [];
  return [
    { label: 'Issues', value: data.value?.total ?? posts.length, unit: '篇' },
    { label: 'Reading', value: posts.reduce((s, p) => s + (p.reading_minutes || 0), 0), unit: '分钟' },
  ];
});
</script>

<template>
  <div v-if="data" class="tag-page" :style="{ '--tag': data.tag.color || 'var(--color-accent)' }">
    <div class="page-shell tag-back">
      <NuxtLink to="/posts" class="back-link"><i aria-hidden="true">←</i> 文章索引</NuxtLink>
    </div>

    <UiPageMasthead en="Tag Archive" label="标签汇聚" :title="data.tag.name" :lede="data.tag.description || undefined" :stats="stats">
      <template #title><span class="tag-hash">#</span>{{ data.tag.name }}</template>
    </UiPageMasthead>

    <div class="page-shell tag-list">
      <ol v-if="data.posts.length" class="entry-list">
        <li v-for="(post, i) in data.posts" :key="post.slug" v-reveal="Math.min(i, 8) * 45" class="reveal">
          <NuxtLink :to="`/posts/${post.slug}`" class="entry-row" data-cursor="read">
            <span class="entry-no">No. {{ issueNo(post.number) }}</span>
            <span class="entry-main">
              <span class="entry-title">{{ post.title }}</span>
              <span v-if="post.subtitle" class="entry-sub">{{ post.subtitle }}</span>
            </span>
            <span />
            <span class="entry-meta">
              <time :datetime="post.published_at">{{ dotDate(post.published_at) }}</time>
              <span>{{ post.reading_minutes }} 分钟</span>
            </span>
            <span class="entry-arrow" aria-hidden="true">→</span>
          </NuxtLink>
        </li>
      </ol>
      <p v-else class="entry-empty">该标签下暂无文章。</p>
    </div>
  </div>
</template>

<style scoped>
.tag-back { padding-top: clamp(28px, 3.5vw, 48px); }
.tag-page :deep(.masthead) { padding-top: clamp(32px, 5vw, 72px); }
.tag-hash {
  margin-right: 0.04em;
  font-family: var(--font-display);
  font-weight: 300;
  font-style: italic;
  color: var(--tag);
}
/* 刊头的墨线即列表的上沿，不再重复画线 */
.tag-list :deep(.entry-list) { border-top: 0; }
</style>
