<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import gsap from 'gsap';
import type { CanvasItem } from '~/components/canvas/InfiniteCanvas.vue';
import { frameLerp } from '~/composables/motion/tokens';
import { useLenis } from '~/composables/useLenis';

useHead({ title: "Luntrix's Editorial · 墨落于水，字成于纸" });

interface TagLite { name: string; slug: string }
interface PostLite {
  id: number;
  slug: string;
  number: number | null;
  title: string;
  subtitle?: string | null;
  excerpt?: string | null;
  published_at?: string | null;
  reading_minutes?: number;
  accent_color?: string | null;
  layout_variant?: string | null;
  tags?: TagLite[];
}
interface ProjectLite { id: number; slug: string; name: string; tagline?: string | null; description?: string | null; language?: string | null; language_color?: string | null; stars?: number | null }
interface TilLite { id: number; title?: string | null; content_md?: string | null; tag?: string | null; created_at?: string | null }

type Filter = 'all' | 'post' | 'project' | 'til';
const viewMode = ref<'canvas' | 'list'>('canvas');
const filter = ref<Filter>('all');
const canvasRef = ref<{ resetView: () => void } | null>(null);

const { data } = await useAsyncData('home', async () => {
  const [posts, projects, tils] = await Promise.all([
    $fetch<{ items: PostLite[] }>('/api/v1/posts', { query: { page_size: 50 } }).catch(() => ({ items: [] as PostLite[] })),
    $fetch<ProjectLite[]>('/api/v1/projects').catch(() => [] as ProjectLite[]),
    $fetch<{ items: TilLite[] }>('/api/v1/til', { query: { page_size: 30 } }).catch(() => ({ items: [] as TilLite[] })),
  ]);
  return { posts: posts.items || [], projects: projects || [], tils: tils.items || [] };
});

const posts = computed<PostLite[]>(() => data.value?.posts || []);
const fmtDate = dotDate;
const plain = (md?: string | null, max = 90) => plainText(md || '', max);

const canvasItems = computed<CanvasItem[]>(() => {
  const d = data.value;
  if (!d) return [];
  const postItems: CanvasItem[] = d.posts.map((p) => ({
    key: `post-${p.id}`,
    kind: 'post',
    href: `/posts/${p.slug}`,
    slug: p.slug,
    title: p.title,
    excerpt: plain(p.excerpt, 120),
    number: p.number,
    meta: `${fmtDate(p.published_at)} · ${p.reading_minutes} 分钟`,
    tags: (p.tags || []).map((t) => t.name),
    accent: p.accent_color,
    layout: p.layout_variant,
  }));
  const projectItems: CanvasItem[] = d.projects.map((p) => ({
    key: `project-${p.id}`,
    kind: 'project',
    href: `/projects/${p.slug}`,
    title: p.name,
    excerpt: p.tagline || p.description || '',
    lang: p.language,
    langColor: p.language_color,
    stars: p.stars,
  }));
  const tilItems: CanvasItem[] = d.tils.slice(0, 16).map((t) => ({
    key: `til-${t.id}`,
    kind: 'til',
    href: '/til',
    title: t.title || plain(t.content_md, 40),
    excerpt: plain(t.content_md, 80),
    tags: t.tag ? [t.tag] : [],
    meta: fmtDate(t.created_at),
  }));
  // 交错混排：文章为主，项目与 TIL 穿插其中
  const out: CanvasItem[] = [];
  const max = Math.max(postItems.length, projectItems.length, tilItems.length);
  for (let i = 0; i < max; i++) {
    if (postItems[i]) out.push(postItems[i]);
    if (tilItems[i]) out.push(tilItems[i]);
    if (projectItems[i]) out.push(projectItems[i]);
  }
  return out;
});

const counts = computed(() => ({
  all: canvasItems.value.length,
  post: posts.value.length,
  project: data.value?.projects.length || 0,
  til: Math.min(data.value?.tils.length || 0, 16),
}));

const filterOptions = computed(() => [
  { value: 'all', label: '全部', count: counts.value.all },
  { value: 'post', label: '文章', count: counts.value.post },
  { value: 'project', label: '项目', count: counts.value.project },
  { value: 'til', label: 'TIL', count: counts.value.til },
]);

const latest = computed(() => posts.value.slice(0, 5).map((p) => ({ ...p, excerpt: plain(p.excerpt, 160) })));

/* ---- 标题：逐字拆开，供 M5 可变字体响应 ---- */
const LINE_A = 'Liquid'.split('');
const LINE_B = 'Editorial'.split('');

/** 序幕播放时标题随幕布揭起逐字凝出；否则直接显示（避免与服务端渲染的标题闪一次） */
const heroIntro = ref(false);
const heroRef = ref<HTMLElement | null>(null);

/*
 * M5 可变字体：每个字母的 wght 随与光标的距离变化，越近越粗——像铅字受压；
 * SOFT 随页面滚动速度变化，滚得越快字形越「软」。两层标题（墨层与朱砂层）同步。
 */
let chars: Array<{ els: HTMLElement[]; x: number; y: number; base: number; peak: number; w: number; soft: number }> = [];
let measuredAt = 0;
let mx = -9999;
let my = -9999;
let lastScroll = 0;
let scrollVel = 0;
let m5Ticker: ((t: number, dt: number) => void) | null = null;

function measureChars() {
  const groups = new Map<string, HTMLElement[]>();
  heroRef.value?.querySelectorAll<HTMLElement>('[data-char]').forEach((el) => {
    const k = el.dataset.char!;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(el);
  });
  measuredAt = window.scrollY;
  chars = [...groups.values()].map((els) => {
    const r = els[0].getBoundingClientRect();
    const base = Number(els[0].dataset.base || 400);
    return { els, x: r.left + r.width / 2, y: r.top + r.height / 2, base, peak: base < 400 ? 720 : 900, w: base, soft: 30 };
  });
}

function onPointer(e: PointerEvent) {
  mx = e.clientX;
  my = e.clientY;
}

function startM5() {
  const root = document.documentElement;
  if (root.classList.contains('reduce-motion') || root.getAttribute('data-pointer') === 'coarse') return;
  measureChars();
  window.addEventListener('pointermove', onPointer, { passive: true });
  window.addEventListener('resize', measureChars, { passive: true });
  lastScroll = window.scrollY;
  m5Ticker = (_t, dt) => {
    const y = window.scrollY;
    scrollVel += ((y - lastScroll) - scrollVel) * frameLerp(0.15, dt);
    lastScroll = y;
    const k = frameLerp(0.16, dt);
    const soft = Math.min(100, 30 + Math.abs(scrollVel) * 4);
    for (const c of chars) {
      // 字的当前视口位置 = 测量时的位置 − 之后滚过的距离
      const d = Math.hypot(mx - c.x, my - (c.y - (y - measuredAt)));
      const target = c.base + (c.peak - c.base) * Math.max(0, 1 - d / 320) ** 1.6;
      c.w += (target - c.w) * k;
      c.soft += (soft - c.soft) * k;
      const v = `"wght" ${c.w.toFixed(0)}, "opsz" 144, "SOFT" ${c.soft.toFixed(0)}`;
      for (const el of c.els) el.style.fontVariationSettings = v;
    }
  };
  gsap.ticker.add(m5Ticker);
}

function onKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  if (e.key === 'l' || e.key === 'L') viewMode.value = viewMode.value === 'canvas' ? 'list' : 'canvas';
}

function scrollDown() {
  const target = document.querySelector<HTMLElement>('#latest');
  if (target) useLenis().scrollTo(target, { offset: -24, duration: 1.4 });
}

onMounted(() => {
  heroIntro.value = !document.documentElement.classList.contains('curtain-seen');
  // 触屏设备默认列表视图（PRD 5.1）
  if (window.matchMedia('(pointer: coarse)').matches) viewMode.value = 'list';
  window.addEventListener('keydown', onKeydown);
  nextTick(() => gsap.delayedCall(0.3, startM5));
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  window.removeEventListener('pointermove', onPointer);
  window.removeEventListener('resize', measureChars);
  if (m5Ticker) gsap.ticker.remove(m5Ticker);
});
</script>

<template>
  <div class="home">
    <!-- ============ 首屏：墨池 ============ -->
    <section ref="heroRef" class="home-hero" :class="`is-${viewMode}`" aria-label="墨池：可拖拽探索的内容画布">
      <ClientOnly v-if="viewMode === 'canvas'">
        <CanvasInfiniteCanvas ref="canvasRef" :items="canvasItems" :filter="filter">
          <template #title="{ layer }">
            <div class="hero-mast" :class="[`layer-${layer}`, { 'is-intro': heroIntro }]">
              <p class="hero-eyebrow"><span>Vol. 2026</span><i aria-hidden="true" />墨落于水 · 字成于纸</p>
              <h1 class="hero-title font-display" :aria-hidden="layer === 'accent' ? 'true' : undefined">
                <span class="hero-line is-a"><span v-for="(c, i) in LINE_A" :key="i" class="hero-char" :data-char="`a${i}`" data-base="620" :style="{ '--i': i }">{{ c }}</span></span>
                <span class="hero-line is-b"><em><span v-for="(c, i) in LINE_B" :key="i" class="hero-char" :data-char="`b${i}`" data-base="280" :style="{ '--i': i + 3 }">{{ c }}</span></em></span>
              </h1>
              <p class="hero-sub">杂志级排版 <i>×</i> 流动的墨 <i>×</i> 会呼吸的光</p>
            </div>
          </template>
        </CanvasInfiniteCanvas>
        <template #fallback>
          <div class="hero-fallback">
            <div class="hero-mast layer-solo">
              <p class="hero-eyebrow"><span>Vol. 2026</span><i aria-hidden="true" />墨落于水 · 字成于纸</p>
              <h1 class="hero-title font-display">
                <span class="hero-line is-a"><span>Liquid</span></span>
                <span class="hero-line is-b"><em>Editorial</em></span>
              </h1>
              <p class="hero-sub">杂志级排版 <i>×</i> 流动的墨 <i>×</i> 会呼吸的光</p>
            </div>
          </div>
        </template>
      </ClientOnly>

      <div v-else class="hero-list">
        <InkPond class="hero-list-pond" :interactive="true" />
        <header class="hero-list-head page-shell">
          <p class="hero-eyebrow"><span>Vol. 2026</span><i aria-hidden="true" />墨落于水 · 字成于纸</p>
          <h1 v-reveal class="hero-list-title font-display reveal-lines">
            <span class="line-mask"><span class="line-inner">Liquid</span></span>
            <span class="line-mask"><span class="line-inner"><em>Editorial</em></span></span>
          </h1>
        </header>
        <ol class="entry-list page-shell hero-list-entries" data-skew>
          <li v-for="(p, i) in posts" :key="p.id" v-reveal="Math.min(i, 6) * 50" class="reveal">
            <NuxtLink :to="`/posts/${p.slug}`" class="entry-row register-focus" data-cursor="read">
              <span class="entry-no">No. {{ issueNo(p.number) }}</span>
              <span class="entry-main"><span class="entry-title">{{ p.title }}</span></span>
              <span class="entry-tags"><span v-for="t in (p.tags || []).slice(0, 2)" :key="t.slug" class="editorial-tag">{{ t.name }}</span></span>
              <span class="entry-meta"><time>{{ fmtDate(p.published_at) }}</time></span>
              <span class="entry-arrow" aria-hidden="true">→</span>
            </NuxtLink>
          </li>
        </ol>
      </div>

      <!-- 底部控制条 -->
      <div class="hero-controls">
        <UiSegmented
          v-if="viewMode === 'canvas'"
          v-model="filter"
          :options="filterOptions"
          aria-label="筛选内容"
          glass
        />
        <div class="pill-group">
          <button v-if="viewMode === 'canvas'" type="button" class="pill" title="回到中心（0）" @click="canvasRef?.resetView()">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="3" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></svg>
            <span class="pill-label">回正</span>
          </button>
          <button type="button" class="pill" :title="'切换视图（L）'" @click="viewMode = viewMode === 'canvas' ? 'list' : 'canvas'">
            <span class="pill-label">{{ viewMode === 'canvas' ? '列表' : '墨池' }}</span> <kbd>L</kbd>
          </button>
        </div>
      </div>
      <p v-if="viewMode === 'canvas'" class="hero-hint" aria-hidden="true">
        <span>拖拽纸笺</span><i />
        <span>搅动墨池</span><i />
        <span>点标题落一点朱砂</span><i />
        <span><kbd>0</kbd> 回正</span>
      </p>
      <button v-if="viewMode === 'canvas'" type="button" class="hero-scroll" aria-label="向下阅读最新特稿" @click="scrollDown">
        <span>向下</span><i aria-hidden="true" />
      </button>
    </section>

    <!-- 给搜索引擎与无脚本环境：全部内容的语义化目录（画布只是它的另一种排版） -->
    <nav class="sr-only" aria-label="全部内容">
      <ul>
        <li v-for="item in canvasItems" :key="item.key"><a :href="item.href">{{ item.title }}</a></li>
      </ul>
    </nav>

    <!-- ============ 最新特稿 ============ -->
    <section id="latest" class="home-latest page-shell" aria-labelledby="latest-title">
      <header class="section-head">
        <p class="eyebrow"><span class="section-no">§ 01</span> Latest Issue · 本期特稿</p>
        <h2 id="latest-title" v-reveal class="section-title reveal-lines">
          <span class="line-mask"><span class="line-inner">新墨未干</span></span>
        </h2>
        <NuxtLink to="/posts" class="section-more">全部特稿 <i aria-hidden="true">→</i></NuxtLink>
      </header>

      <div class="latest-grid" data-skew>
        <NuxtLink
          v-for="(p, i) in latest"
          :key="p.id"
          v-reveal="(i % 3) * 60"
          :to="`/posts/${p.slug}`"
          class="latest-card reveal register-focus"
          :class="{ 'is-lead': i === 0 }"
          :style="p.accent_color ? { '--card-accent': p.accent_color } : undefined"
          data-cursor="read"
        >
          <span class="latest-cover">
            <InkCover :seed="p.slug" :no="p.number" :accent="p.accent_color" :width="i === 0 ? 800 : 400" :height="i === 0 ? 460 : 250" :numeral="i === 0" />
          </span>
          <span class="latest-body">
            <span class="latest-meta">
              <span class="latest-no">No. {{ issueNo(p.number) }}</span>
              <span v-for="t in (p.tags || []).slice(0, 2)" :key="t.slug">{{ t.name }}</span>
              <span>{{ fmtDate(p.published_at) }}</span>
            </span>
            <span class="latest-title">{{ p.title }}</span>
            <span v-if="p.excerpt && i === 0" class="latest-excerpt">{{ p.excerpt }}</span>
            <span class="latest-foot">{{ p.reading_minutes }} 分钟阅读 <i aria-hidden="true">→</i></span>
          </span>
        </NuxtLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ---------------- 首屏 ---------------- */
.home-hero {
  position: relative;
  height: calc(100svh - var(--header-h));
  min-height: 560px;
  border-bottom: 1px solid var(--color-line);
}
.home-hero.is-list { height: auto; min-height: 0; padding-bottom: 112px; }

.hero-mast { display: flex; flex-direction: column; align-items: center; text-align: center; }
/* 两层标题：墨层只显示墨字，朱砂层只显示朱砂斜体，其余占位保持排版一致 */
.layer-ink .hero-line.is-b em,
.layer-accent .hero-line.is-a,
.layer-accent .hero-eyebrow,
.layer-accent .hero-sub { visibility: hidden; }
.layer-ink .hero-eyebrow span { color: inherit; }

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--mast-muted, var(--color-ink-muted));
}
.hero-eyebrow span { color: var(--color-accent-text); }
.hero-eyebrow i { width: 28px; height: 1px; background: currentColor; opacity: 0.4; }
.hero-title {
  margin-top: 18px;
  font-size: clamp(72px, 13vw, 220px);
  font-weight: 800;
  line-height: 0.86;
  letter-spacing: -0.05em;
  text-align: center;
  font-variation-settings: "opsz" 144, "SOFT" 30;
}
.hero-line { display: block; padding: 0 0.06em 0.1em; margin-bottom: -0.1em; }
.hero-char { display: inline-block; }
.hero-line.is-a .hero-char { font-variation-settings: "wght" 620, "opsz" 144, "SOFT" 30; }
.hero-line.is-b .hero-char { font-variation-settings: "wght" 280, "opsz" 144, "SOFT" 100; }
.layer-solo .hero-line.is-a > span { font-weight: 620; }
.hero-title em {
  font-style: italic;
  font-weight: 300;
  color: var(--color-accent);
  font-variation-settings: "opsz" 144, "SOFT" 100;
}
.layer-solo .hero-title em { color: var(--color-accent); }
.hero-sub {
  margin-top: 28px;
  font-family: var(--font-serif);
  font-size: clamp(15px, 1.3vw, 19px);
  color: var(--mast-muted, var(--color-ink-muted));
  letter-spacing: 0.08em;
}
.hero-sub i { font-style: normal; margin-inline: 0.3em; opacity: 0.6; }

/* 入场：每个字母从墨里「凝」出来——从模糊、下沉、细笔画到清晰 */
html.motion-ready .hero-char { animation: char-settle 1300ms var(--ease-out-expo) backwards; animation-delay: calc(var(--i) * 55ms + 120ms); }
html.motion-ready .is-intro .hero-char { animation-delay: calc(var(--i) * 55ms + 1.1s); }
@keyframes char-settle {
  from { opacity: 0; transform: translate3d(0, 0.18em, 0) scale(1.04); filter: blur(10px); }
  60% { filter: blur(0); }
}
html.motion-ready .hero-eyebrow,
html.motion-ready .hero-sub { animation: hero-fade 1100ms var(--ease-out-quart) backwards 500ms; }
html.motion-ready .is-intro .hero-eyebrow,
html.motion-ready .is-intro .hero-sub { animation-delay: 1.5s; }
@keyframes hero-fade { from { opacity: 0; transform: translate3d(0, 10px, 0); } }
html.reduce-motion .hero-mast * { animation: none !important; }

.hero-fallback {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.hero-controls {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 24px;
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  padding-inline: 16px;
  pointer-events: none;
}
.hero-controls > * { pointer-events: auto; }
.is-list .hero-controls { bottom: 40px; }
.pill-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  background: var(--color-paper-glass);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
  -webkit-backdrop-filter: blur(14px) saturate(1.5);
  backdrop-filter: blur(14px) saturate(1.5);
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 14px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-micro);
  font-weight: 500;
  color: var(--color-ink-muted);
  white-space: nowrap;
  transition: color var(--dur-micro) ease, background-color var(--dur-sm) var(--ease-out-quart), transform var(--dur-impress) var(--ease-impress);
}
.pill:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 5%, transparent); }
.pill:active { transform: scale(0.95); }
.pill svg { transition: transform 700ms var(--ease-spring); }
.pill:hover svg { transform: rotate(90deg); }
.pill kbd { font-size: 9px; }

.hero-hint {
  position: absolute;
  top: 20px;
  left: 50%;
  z-index: 3;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  height: 28px;
  padding: 0 14px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  color: var(--color-ink-muted);
  background: var(--color-paper-glass);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  pointer-events: none;
  white-space: nowrap;
}
.hero-hint i { width: 3px; height: 3px; border-radius: 50%; background: currentColor; opacity: 0.6; }
.hero-hint span { display: inline-flex; align-items: center; gap: 4px; }
.hero-hint kbd { font-size: 9px; }

/* 向下：一滴墨沿细线往下淌 */
.hero-scroll {
  position: absolute;
  left: 50%;
  bottom: 84px;
  z-index: 4;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--color-ink-muted);
}
.hero-scroll i {
  position: relative;
  width: 1px;
  height: 36px;
  background: var(--color-line-strong);
  overflow: hidden;
}
.hero-scroll i::after {
  content: "";
  position: absolute;
  left: -1.5px;
  top: 0;
  width: 4px;
  height: 8px;
  border-radius: 2px 2px 50% 50%;
  background: var(--color-ink);
  animation: drip 2.6s var(--ease-in-quart) infinite;
}
@keyframes drip {
  0% { transform: translateY(-10px); opacity: 0; }
  20% { opacity: 1; }
  100% { transform: translateY(40px); opacity: 0; }
}
html.reduce-motion .hero-scroll i::after { animation: none; transform: translateY(14px); }

@media (max-width: 760px) {
  .hero-hint { display: none; }
  .hero-scroll { display: none; }
}
@media (max-width: 420px) {
  .pill-label { display: none; }
  .pill { padding: 0 10px; }
}

/* 列表视图：标题下也是一方小墨池 */
.hero-list { position: relative; }
.hero-list-pond { height: 420px; bottom: auto; }
.hero-list-head { position: relative; padding-block: 72px 40px; }
.hero-list-title {
  margin-top: 14px;
  font-size: clamp(56px, 12vw, 160px);
  font-weight: 800;
  line-height: 0.9;
  letter-spacing: -0.045em;
}
.hero-list-title em { font-style: italic; font-weight: 300; color: var(--color-accent); font-variation-settings: "opsz" 144, "SOFT" 100; }
.hero-list-entries { position: relative; }

/* ---------------- 最新特稿 ---------------- */
.home-latest { padding-top: var(--space-24); }
.section-head {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
  gap: 10px 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--color-ink);
}
.section-head .eyebrow { grid-column: 1 / -1; }
.section-no { margin-right: 6px; color: var(--color-accent-text); }
.section-title {
  font-family: var(--font-serif);
  font-size: clamp(34px, 4.4vw, 64px);
  font-weight: 900;
  line-height: 1.02;
  letter-spacing: -0.025em;
}
.section-more {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 16px;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-xs);
  font-size: var(--fs-micro);
  color: var(--color-ink);
  transition: background-color var(--dur-sm) var(--ease-out-quart), color var(--dur-sm) var(--ease-out-quart), border-color var(--dur-sm) ease;
}
.section-more i { font-style: normal; transition: transform 600ms var(--ease-out-expo); }
.section-more:hover { background: var(--color-ink); border-color: var(--color-ink); color: var(--color-bg); }
.section-more:hover i { transform: translateX(4px); }

.latest-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  background: var(--color-line);
  border: 1px solid var(--color-line);
  border-top: 0;
}
.latest-card {
  --card-accent: var(--color-accent);
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  overflow: hidden;
}
.latest-card.is-lead { grid-column: span 2; grid-row: span 2; }
.latest-cover {
  position: relative;
  display: block;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  border-bottom: 1px solid var(--color-line);
}
.is-lead .latest-cover { aspect-ratio: 16 / 9.2; }
.latest-cover :deep(.ink-cover) { transition: transform 1400ms var(--ease-out-expo), filter 900ms var(--ease-out-quart); }
.latest-card:hover .latest-cover :deep(.ink-cover) { transform: scale(1.05); }
/* 悬停：一道墨线从纸面左上角洇入 */
.latest-card::after {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  width: 2px;
  height: 100%;
  background: var(--card-accent);
  transform: scaleY(0);
  transform-origin: 50% 0;
  transition: transform 900ms var(--ease-out-expo);
}
.latest-card:hover::after { transform: scaleY(1); }
.latest-body { display: flex; flex-direction: column; gap: 12px; padding: 22px 24px 26px; flex: 1; }
.is-lead .latest-body { padding: 28px 32px 32px; }
.latest-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
}
.latest-no { color: var(--color-accent-text); }
.latest-meta span:last-child { margin-left: auto; }
.latest-title {
  font-family: var(--font-serif);
  font-size: 19px;
  font-weight: 700;
  line-height: 1.42;
  transition: transform 700ms var(--ease-out-expo);
}
.latest-card:hover .latest-title { transform: translateX(4px); }
.is-lead .latest-title { font-size: clamp(26px, 2.8vw, 42px); line-height: 1.22; letter-spacing: -0.015em; max-width: 18em; }
.latest-excerpt {
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.85;
  color: var(--color-ink-muted);
  max-width: 38em;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.latest-foot { display: inline-flex; align-items: center; gap: 6px; margin-top: auto; font-size: var(--fs-micro); color: var(--color-ink-muted); }
.latest-foot i { display: inline-block; font-style: normal; color: var(--card-accent); transition: transform 600ms var(--ease-out-expo); }
.latest-card:hover .latest-foot i { transform: translateX(6px); }

@media (max-width: 1080px) {
  .latest-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .latest-grid { grid-template-columns: 1fr; }
  .latest-card.is-lead { grid-column: auto; grid-row: auto; }
  .section-more { grid-column: 1 / -1; justify-self: start; }
}
</style>
