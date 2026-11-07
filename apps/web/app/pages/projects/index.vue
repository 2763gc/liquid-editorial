<script setup lang="ts">
import { computed } from 'vue';
import { pigmentFor } from '~/utils/pigment';

/** 网点密度随光标位置变化：只在悬停时写两个变量 */
function onCardMove(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement;
  const r = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${(((e.clientX - r.left) / r.width) * 100).toFixed(1)}%`);
  el.style.setProperty('--my', `${(((e.clientY - r.top) / r.height) * 100).toFixed(1)}%`);
}

useHead({ title: "开源项目 · Luntrix's Editorial" });

const { data: projects } = await useFetch<any[]>('/api/v1/projects', { default: () => [] });

const stats = computed(() => {
  const list = projects.value || [];
  return [
    { label: 'Projects', value: list.length, unit: '个' },
    { label: 'Stars', value: compactNumber(list.reduce((s, p) => s + (p.stars || 0), 0)), unit: '★' },
    { label: 'Languages', value: new Set(list.map((p) => p.language).filter(Boolean)).size, unit: '种' },
  ];
});
</script>

<template>
  <div class="projects-page">
    <UiPageMasthead
      index="04"
      en="Open Source Repertory"
      label="开源作品集"
      title="开源项目"
      lede="从系统运行时、存储引擎到排版工具库。每一个仓库都是一次对「好代码长什么样」的回答。"
      :stats="stats"
    />

    <div class="page-shell">
      <div v-if="projects?.length" class="project-grid hairline-grid">
        <article
          v-for="(proj, i) in projects"
          :key="proj.slug"
          v-reveal="(i % 2) * 80"
          class="project-card reveal"
          :style="{ '--lang': pigmentFor(proj.language_color).color }"
          @pointermove="onCardMove"
        >
          <span class="project-glyph font-display" aria-hidden="true">{{ (proj.name || 'Aa').slice(0, 2) }}</span>
          <pre v-if="proj.code_snippet" class="project-texture" aria-hidden="true"><code>{{ proj.code_snippet }}</code></pre>

          <div class="project-top">
            <span class="project-index">P/{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="status-mark" :class="proj.status === 'active' ? 'is-live' : ''">{{ proj.status === 'active' ? 'Active' : proj.status }}</span>
          </div>

          <h2 class="project-name">
            <NuxtLink :to="`/projects/${proj.slug}`" class="project-link" data-cursor="open">{{ proj.name }}</NuxtLink>
          </h2>
          <p class="project-tagline">{{ proj.tagline }}</p>

          <div class="project-foot">
            <span class="project-lang"><i aria-hidden="true" />{{ proj.language || 'Code' }}</span>
            <span class="project-num">★ {{ compactNumber(proj.stars) }}</span>
            <span class="project-num">⑂ {{ compactNumber(proj.forks) }}</span>
            <a v-if="proj.repo_url" :href="proj.repo_url" target="_blank" rel="noopener" class="project-repo link-draw">GitHub ↗</a>
            <span class="project-go" aria-hidden="true">详情 <i>→</i></span>
          </div>
        </article>
      </div>
      <div v-else class="empty-note">
        <span class="empty-note-glyph" aria-hidden="true">Aa</span>
        <p class="empty-note-text">字模还在雕刻。第一个开源仓库公开之后，会在这里排出它的样张。</p>
        <p class="empty-note-meta">$ gh repo list --public → 0</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.project-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: clamp(32px, 4vw, 56px);
}
.project-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 320px;
  padding: clamp(24px, 2.6vw, 36px);
  overflow: hidden;
  isolation: isolate;
  transition: background-color 500ms var(--ease-out-quart);
}
/* 顶部语言色细线：悬停时从左绘入 */
.project-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--lang);
  transform: scaleX(0);
  transform-origin: 0 50%;
  transition: transform 800ms var(--ease-out-expo);
}
.project-card:hover::before { transform: scaleX(1); }
.project-card:hover { background: color-mix(in srgb, var(--color-bg) 97%, var(--color-ink)); }

/* 背景代码纹理 */
.project-texture {
  position: absolute;
  right: -12px;
  bottom: -8px;
  z-index: -1;
  max-width: 70%;
  font-size: 10.5px;
  line-height: 1.55;
  color: var(--color-ink);
  opacity: 0.045;
  white-space: pre;
  overflow: hidden;
  pointer-events: none;
  user-select: none;
  mask-image: linear-gradient(to top left, #000 30%, transparent 85%);
  -webkit-mask-image: linear-gradient(to top left, #000 30%, transparent 85%);
  transition: opacity 700ms var(--ease-out-quart), transform 1200ms var(--ease-out-expo);
}
.project-card:hover .project-texture { opacity: 0.1; transform: translate3d(-8px, -6px, 0); }

.project-top { display: flex; align-items: center; justify-content: space-between; }
.project-index { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; color: var(--color-accent); }

.project-name {
  margin-top: clamp(28px, 4vw, 56px);
  font-family: var(--font-mono);
  font-size: clamp(22px, 2.3vw, 32px);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.03em;
}
/* 整张卡片可点：链接的伪元素铺满卡片，GitHub 链接浮在其上 */
.project-link::after { content: ""; position: absolute; inset: 0; z-index: 0; }
.project-link:focus-visible { outline: none; }
.project-link:focus-visible::after { outline: 1.5px solid var(--color-accent); outline-offset: -4px; }

.project-tagline {
  margin-top: 12px;
  max-width: 30em;
  font-family: var(--font-serif);
  font-size: 15.5px;
  line-height: 1.8;
  color: var(--color-ink-muted);
}

.project-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 18px;
  margin-top: auto;
  padding-top: 28px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-ink-muted);
}
.project-lang { display: inline-flex; align-items: center; gap: 7px; color: var(--color-ink); }
.project-lang i { width: 8px; height: 8px; border-radius: 50%; background: var(--lang); }
.project-num { font-variant-numeric: tabular-nums; }
/* 语言与数据靠左，链接靠右 */
.project-foot > :nth-child(3) { margin-right: auto; }
.project-repo { position: relative; z-index: 1; }
.project-go { color: var(--color-ink); }
.project-go i { display: inline-block; font-style: normal; color: var(--color-accent); transition: transform 600ms var(--ease-out-expo); }
.project-card:hover .project-go i { transform: translateX(5px); }

@media (max-width: 760px) {
  .project-grid { grid-template-columns: 1fr; }
  .project-card { min-height: 260px; }
}
/* 手机上整张卡片已可点进详情（详情页有源码按钮），收起行内 GitHub 链接保持一行 */
@media (max-width: 480px) {
  .project-repo { display: none; }
}

/* ---------------- 字模样张（v2） ---------------- */
.project-card { min-height: 360px; }
/* 网点：密度随光标位置变化（遮罩中心跟着光标走） */
.project-card::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image: radial-gradient(circle, color-mix(in oklab, var(--lang) 55%, transparent) 1.1px, transparent 1.6px);
  background-size: 7px 7px;
  -webkit-mask-image: radial-gradient(circle at var(--mx, 50%) var(--my, 50%), #000, transparent 46%);
  mask-image: radial-gradient(circle at var(--mx, 50%) var(--my, 50%), #000, transparent 46%);
  opacity: 0;
  transition: opacity 600ms var(--ease-out-quart);
}
.project-card:hover::after { opacity: 1; }
.project-glyph {
  position: absolute;
  right: -0.06em;
  bottom: -0.22em;
  z-index: -1;
  font-size: clamp(140px, 16vw, 260px);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.06em;
  color: transparent;
  -webkit-text-stroke: 1px color-mix(in oklab, var(--lang) 45%, transparent);
  font-variation-settings: "opsz" 144, "SOFT" 0;
  transition: font-variation-settings 900ms var(--ease-out-expo), transform 900ms var(--ease-out-expo);
  pointer-events: none;
}
.project-card:hover .project-glyph { font-variation-settings: "opsz" 144, "SOFT" 100; transform: translate3d(-8px, -6px, 0); }
.project-name { font-family: var(--font-display); font-size: clamp(36px, 4.4vw, 68px); font-weight: 600; line-height: 1; letter-spacing: -0.035em; font-variation-settings: "opsz" 144, "SOFT" 50; }
.project-num { font-variant-numeric: tabular-nums lining-nums; }
</style>
