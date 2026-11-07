<script setup lang="ts">
import { computed } from 'vue';

const route = useRoute();
const slug = computed(() => String(route.params.slug || ''));

/* 描述由 Nitro 服务端渲染（Shiki 不进浏览器包），见 server/api/content/projects/[slug].get.ts */
const { data: project, error } = await useFetch<any>(() => `/api/content/projects/${encodeURIComponent(slug.value)}`, {
  key: `project-${slug.value}`,
});

if (error.value) {
  throw createError({
    statusCode: error.value.statusCode === 404 ? 404 : 500,
    statusMessage: error.value.statusCode === 404 ? '项目不存在' : '项目加载失败',
    fatal: true,
  });
}

useSeoMeta({
  title: () => (project.value ? `${project.value.name} · 开源项目` : '开源项目'),
  description: () => project.value?.tagline || '',
});

const stats = computed(() => {
  const p = project.value;
  if (!p) return [];
  return [
    { label: 'Stars', value: compactNumber(p.stars), unit: '★' },
    { label: 'Forks', value: compactNumber(p.forks), unit: '⑂' },
    { label: 'Language', value: p.language || '—' },
  ];
});
</script>

<template>
  <div v-if="project" class="project-detail" :style="{ '--lang': project.language_color || 'var(--color-accent)' }">
    <div class="page-shell project-back">
      <NuxtLink to="/projects" class="back-link"><i aria-hidden="true">←</i> 开源项目</NuxtLink>
    </div>

    <UiPageMasthead en="Project" :label="project.language" :title="project.name" :lede="project.tagline" :stats="stats">
      <template #kicker>
        <span class="status-mark" :class="project.status === 'active' ? 'is-live' : ''">{{ project.status === 'active' ? 'Active' : project.status }}</span>
      </template>
      <div class="project-actions">
        <a v-if="project.repo_url" :href="project.repo_url" target="_blank" rel="noopener" class="btn btn-solid">
          查看源码 <span class="btn-arrow is-up" aria-hidden="true">↗</span>
        </a>
        <a v-if="project.homepage_url" :href="project.homepage_url" target="_blank" rel="noopener" class="btn">
          在线演示 <span class="btn-arrow is-up" aria-hidden="true">↗</span>
        </a>
      </div>
    </UiPageMasthead>

    <div class="page-shell">
      <article class="article-prose project-prose" v-html="project.html" />
    </div>
  </div>
</template>

<style scoped>
.project-back { padding-top: clamp(28px, 3.5vw, 48px); }
.project-detail :deep(.masthead) { padding-top: clamp(32px, 5vw, 72px); }
.project-detail :deep(.masthead-title) { font-family: var(--font-mono); font-weight: 600; letter-spacing: -0.045em; font-size: clamp(36px, 6vw, 92px); }
.project-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.project-actions .btn { height: 44px; padding: 0 22px; }
.project-prose { max-width: var(--content-max-width); margin: clamp(48px, 6vw, 88px) auto 0; }
</style>
