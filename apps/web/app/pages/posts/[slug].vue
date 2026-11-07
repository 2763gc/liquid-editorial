<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';
import { useLenis, lockScroll, unlockScroll } from '~/composables/useLenis';
import { useProse } from '~/composables/useProse';
import { useInkSettle } from '~/composables/motion/useInkSettle';
import { useMotion } from '~/composables/useMotion';
import { prefetchJson } from '~/utils/prefetch';
import { pigmentFor } from '~/utils/pigment';
import { inkArt, variantForLayout } from '~/utils/inkArt';

interface TocItem { level: number; text: string; anchor: string }
interface PostDetail {
  id: number;
  slug: string;
  number: number | null;
  title: string;
  subtitle?: string | null;
  excerpt?: string | null;
  html: string;
  toc: TocItem[];
  layout_variant?: string | null;
  accent_color?: string | null;
  published_at?: string | null;
  content_updated_at?: string | null;
  word_count?: number;
  reading_minutes?: number;
  view_count?: number;
  like_count?: number;
  liked?: boolean;
  allow_comments?: boolean;
  tags?: Array<{ name: string; slug: string }>;
  series?: { slug: string; title: string; order?: number | null; total?: number | null } | null;
  prev?: { slug: string; title: string } | null;
  next?: { slug: string; title: string } | null;
  cover?: { url: string } | null;
}
interface Related { id: number; slug: string; number: number | null; title: string }

const route = useRoute();
const slug = computed(() => String(route.params.slug || ''));
const { scrollTo } = useLenis();
const motion = useMotion();

/* 正文由 Nitro 服务端渲染（Shiki 不进浏览器包）；悬停链接时已预取过就直接复用 */
const { data: post, error } = await useAsyncData<PostDetail>(
  () => `post-${slug.value}`,
  () => prefetchJson<PostDetail>(`/api/content/posts/${encodeURIComponent(slug.value)}`),
  { watch: [slug] },
);

if (error.value) {
  throw createError({
    statusCode: error.value.statusCode === 404 ? 404 : 500,
    statusMessage: error.value.statusCode === 404 ? '文章不存在' : '文章加载失败',
    fatal: true,
  });
}

const no = computed(() => String(post.value?.number || 0).padStart(3, '0'));
const layout = computed<string>(() => post.value?.layout_variant || 'standard');
const pigment = computed(() => pigmentFor(post.value?.accent_color));
const variant = computed(() => variantForLayout(layout.value));
const variantName = computed(() => ({ mountain: '远山', bloom: '墨晕', stroke: '皴笔', branch: '折枝', moon: '孤月' } as const)[inkArt(slug.value, 400, 250, variant.value).variant]);
/** 设色：强调色就近映射为传统颜料；夜间换成同色相的亮版本 */
const accentStyle = computed(() => ({
  '--post-accent': pigment.value.color,
  '--post-accent-text': pigment.value.text,
  '--post-accent-night': pigment.value.night,
}));

useSeoMeta({
  title: () => (post.value ? `${post.value.title} · Luntrix's Editorial` : "Luntrix's Editorial"),
  description: () => post.value?.excerpt || post.value?.subtitle || '',
  ogTitle: () => post.value?.title,
  ogDescription: () => post.value?.excerpt || '',
  ogType: 'article',
  ogImage: () => post.value?.cover?.url,
  articlePublishedTime: () => post.value?.published_at || undefined,
});

function fmtDate(iso?: string | null) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${y} 年 ${Number(m)} 月 ${Number(d)} 日`;
}
const updatedLabel = computed(() => {
  const u = post.value?.content_updated_at;
  if (!u || u.slice(0, 10) === post.value?.published_at?.slice(0, 10)) return '';
  return fmtDate(u);
});
const staleDays = ref(0);

/* ---------------- 读屏播报 ---------------- */
const announcement = ref('');
function announce(msg: string) {
  announcement.value = '';
  nextTick(() => { announcement.value = msg; });
}

/* ---------------- 凝字标题 ---------------- */
const titleRef = ref<HTMLElement | null>(null);
useInkSettle(titleRef, { strength: 80, duration: 1.4, delay: 0.05 });

/* ---------------- 阅读进度：顶端一笔墨，笔锋停在读到的位置 ---------------- */
const brushRef = ref<HTMLElement | null>(null);
const percentRef = ref<HTMLElement | null>(null);
const articleRef = ref<HTMLElement | null>(null);
const proseRef = ref<HTMLElement | null>(null);
let lastPercent = -1;
let geom = { start: 0, total: 1 };
/* 图解版式里破栏的代码 / 表格会从侧栏底下穿过：穿过时侧栏让位（淡出），几何在 measure 里一次量好，滚动时只做比较 */
const asideRef = ref<HTMLElement | null>(null);
const asideYield = ref(false);
let breakouts: Array<[number, number]> = [];
let asideBand = { top: 0, height: 0, start: 0 };
function measure() {
  const el = articleRef.value;
  if (!el) return;
  const r = el.getBoundingClientRect();
  geom = { start: r.top + window.scrollY, total: Math.max(1, r.height - window.innerHeight * 0.6) };
  breakouts = [];
  const sticky = asideRef.value?.querySelector<HTMLElement>('.post-aside-sticky');
  const prose = proseRef.value;
  if (layout.value !== 'wide' || !sticky || !prose || !matchMedia('(min-width: 1280px)').matches) return;
  const right = prose.getBoundingClientRect().right;
  for (const b of prose.querySelectorAll<HTMLElement>(':scope > .code-block, :scope > .code-group, :scope > .table-wrap')) {
    const br = b.getBoundingClientRect();
    if (br.right > right + 1) breakouts.push([br.top + window.scrollY, br.bottom + window.scrollY]);
  }
  // start：侧栏还没吸顶时所在的位置（文档坐标）
  asideBand = { top: parseFloat(getComputedStyle(sticky).top) || 0, height: sticky.offsetHeight, start: asideRef.value!.getBoundingClientRect().top + window.scrollY };
}
function onScroll() {
  if (breakouts.length || asideYield.value) {
    const top = Math.max(window.scrollY + asideBand.top, asideBand.start) - 24;
    const bottom = top + asideBand.height + 48;
    asideYield.value = breakouts.some(([t, b]) => t < bottom && b > top);
  }
  const p = Math.min(1, Math.max(0, (window.scrollY - geom.start + window.innerHeight * 0.2) / geom.total));
  if (brushRef.value) brushRef.value.style.transform = `translate3d(${((p - 1) * 100).toFixed(2)}%, 0, 0)`;
  const pct = Math.round(p * 100);
  if (pct !== lastPercent && percentRef.value) {
    lastPercent = pct;
    percentRef.value.textContent = String(pct).padStart(2, '0');
  }
}

/* ---------------- 阅读设置（宽屏在侧栏，≤1080px 由右下角的「Aa」打开） ---------------- */
const fontScale = ref(1);
const fontFamily = ref<'serif' | 'sans'>('serif');
const measureLevel = ref<'narrow' | 'normal' | 'wide'>('normal');
const ligatures = ref(true);
const settingsOpen = ref(false);
function persistReading() {
  try { localStorage.setItem('blog_reading', JSON.stringify({ s: fontScale.value, f: fontFamily.value, m: measureLevel.value, l: ligatures.value })); } catch {}
  gsap.delayedCall(0.05, () => { measure(); useLenis().getLenis()?.resize(); });
}
function setScale(delta: number) {
  fontScale.value = Math.min(1.2, Math.max(0.9, +(fontScale.value + delta).toFixed(2)));
  persistReading();
}
function setFamily(f: string) { fontFamily.value = f === 'sans' ? 'sans' : 'serif'; persistReading(); }
function setMeasure(m: string) { measureLevel.value = (['narrow', 'normal', 'wide'].includes(m) ? m : 'normal') as typeof measureLevel.value; persistReading(); }
function toggleLigatures() { ligatures.value = !ligatures.value; persistReading(); }
const familyOptions = [{ value: 'serif', label: '宋体' }, { value: 'sans', label: '黑体' }];
const measureOptions = [{ value: 'narrow', label: '窄' }, { value: 'normal', label: '中' }, { value: 'wide', label: '宽' }];

/* ---------------- 图片灯箱：从原位放大，滚轮 / 双指缩放、拖动、左右切换、Esc 关闭 ---------------- */
const lightbox = ref<{ src: string; alt: string; index: number } | null>(null);
const lightboxImg = ref<HTMLImageElement | null>(null);
const imageCount = ref(0);
let images: HTMLImageElement[] = [];
let lbFrom: HTMLImageElement | null = null;
const zoom = { s: 1, x: 0, y: 0 };
const pointers = new Map<number, { x: number; y: number }>();
let pinch0 = 0;
let s0 = 1;

function applyZoom() {
  if (lightboxImg.value) gsap.to(lightboxImg.value, { scale: zoom.s, x: zoom.x, y: zoom.y, duration: 0.35, ease: 'outExpo', overwrite: 'auto' });
}
async function openLightbox(img: HTMLImageElement) {
  images = Array.from(proseRef.value?.querySelectorAll<HTMLImageElement>('img') || []);
  imageCount.value = images.length;
  lbFrom = img;
  zoom.s = 1; zoom.x = 0; zoom.y = 0;
  lightbox.value = { src: img.currentSrc || img.src, alt: img.alt, index: images.indexOf(img) };
  lockScroll();
  await nextTick();
  const big = lightboxImg.value;
  if (!big || motion.state.reduced) return;
  const from = img.getBoundingClientRect();
  const to = big.getBoundingClientRect();
  gsap.fromTo(big,
    { x: from.left + from.width / 2 - (to.left + to.width / 2), y: from.top + from.height / 2 - (to.top + to.height / 2), scale: from.width / Math.max(1, to.width) },
    { x: 0, y: 0, scale: 1, duration: 0.7, ease: 'outExpo' });
}
function closeLightbox() {
  const big = lightboxImg.value;
  const img = lbFrom;
  const done = () => { lightbox.value = null; unlockScroll(); };
  if (!big || !img || motion.state.reduced) return done();
  const from = img.getBoundingClientRect();
  gsap.set(big, { scale: 1, x: 0, y: 0 });
  const to = big.getBoundingClientRect();
  gsap.to(big, {
    x: from.left + from.width / 2 - (to.left + to.width / 2),
    y: from.top + from.height / 2 - (to.top + to.height / 2),
    scale: from.width / Math.max(1, to.width),
    duration: 0.45,
    ease: 'inOutQuart',
    onComplete: done,
  });
}
function step(delta: number) {
  if (!lightbox.value || images.length < 2) return;
  const i = (lightbox.value.index + delta + images.length) % images.length;
  const img = images[i];
  lbFrom = img;
  zoom.s = 1; zoom.x = 0; zoom.y = 0;
  lightbox.value = { src: img.currentSrc || img.src, alt: img.alt, index: i };
  if (lightboxImg.value) gsap.fromTo(lightboxImg.value, { opacity: 0, x: delta * 40 }, { opacity: 1, x: 0, scale: 1, duration: 0.5, ease: 'outExpo' });
}
function onLbWheel(e: WheelEvent) {
  e.preventDefault();
  zoom.s = Math.min(4, Math.max(1, zoom.s * (e.deltaY < 0 ? 1.12 : 0.89)));
  if (zoom.s === 1) { zoom.x = 0; zoom.y = 0; }
  applyZoom();
}
function onLbDown(e: PointerEvent) {
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    pinch0 = Math.hypot(a.x - b.x, a.y - b.y);
    s0 = zoom.s;
  }
}
function onLbMove(e: PointerEvent) {
  const prev = pointers.get(e.pointerId);
  if (!prev) return;
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pointers.size === 2) {
    const [a, b] = [...pointers.values()];
    zoom.s = Math.min(4, Math.max(1, (s0 * Math.hypot(a.x - b.x, a.y - b.y)) / Math.max(1, pinch0)));
  } else if (zoom.s > 1) {
    zoom.x += e.clientX - prev.x;
    zoom.y += e.clientY - prev.y;
  }
  applyZoom();
}
function onLbUp(e: PointerEvent) { pointers.delete(e.pointerId); }
function onLbClick(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.lightbox-nav')) return;
  if (zoom.s === 1) closeLightbox();
}

/* ---------------- 正文增强 ---------------- */
const { enhance, copyText } = useProse(proseRef, { onImage: openLightbox, announce });

/* ---------------- 分享：复制链接 / 系统分享面板 ---------------- */
const shared = ref(false);
async function share() {
  const url = location.href.split('#')[0];
  const nav = navigator as Navigator & { share?: (d: ShareData) => Promise<void> };
  if (nav.share && matchMedia('(pointer: coarse)').matches) {
    try { await nav.share({ title: post.value?.title, url }); return; } catch {}
  }
  const ok = await copyText(url);
  shared.value = ok;
  announce(ok ? '链接已复制' : '复制失败');
  window.setTimeout(() => { shared.value = false; }, 1800);
}

/* ---------------- 记住阅读位置 ---------------- */
const resumeAt = ref(0);
function posKey() { return `blog_pos_${slug.value}`; }
function savePosition() {
  try {
    const h = document.documentElement.scrollHeight - window.innerHeight;
    const ratio = h > 0 ? window.scrollY / h : 0;
    if (ratio > 0.08 && ratio < 0.95) localStorage.setItem(posKey(), String(ratio));
    else localStorage.removeItem(posKey());
  } catch {}
}
function resume() {
  const h = document.documentElement.scrollHeight - window.innerHeight;
  scrollTo(h * resumeAt.value, { offset: 0, duration: 1.4 });
  resumeAt.value = 0;
}

/* ---------------- 专栏已读 ---------------- */
function markRead() {
  if (!post.value?.series) return;
  try {
    const key = `blog_series_read_${post.value.series.slug}`;
    const read = new Set<string>(JSON.parse(localStorage.getItem(key) || '[]'));
    read.add(post.value.slug);
    localStorage.setItem(key, JSON.stringify([...read]));
  } catch {}
}

/* ---------------- 相关文章 ---------------- */
const related = ref<Related[]>([]);

function init() {
  if (!post.value) return;
  const stamp = post.value.content_updated_at || post.value.published_at;
  staleDays.value = stamp ? Math.floor((Date.now() - new Date(stamp).getTime()) / 86400000) : 0;
  nextTick(() => {
    enhance();
    measure();
    onScroll();
  });
  try {
    const saved = Number(localStorage.getItem(posKey()) || 0);
    resumeAt.value = !location.hash && saved > 0.08 ? saved : 0;
  } catch {}
  $fetch(`/api/v1/posts/${encodeURIComponent(slug.value)}/view`, { method: 'POST' }).catch(() => {});
  $fetch<Related[]>(`/api/v1/posts/${encodeURIComponent(slug.value)}/related`).then((r) => { related.value = r || []; }).catch(() => {});
  markRead();
}

watch(slug, () => nextTick(init));

let ro: ResizeObserver | null = null;
function onKeydown(e: KeyboardEvent) {
  if (!lightbox.value) {
    if (e.key === 'Escape' && settingsOpen.value) settingsOpen.value = false;
    return;
  }
  if (e.key === 'Escape') closeLightbox();
  else if (e.key === 'ArrowRight') step(1);
  else if (e.key === 'ArrowLeft') step(-1);
}

onMounted(() => {
  try {
    const r = JSON.parse(localStorage.getItem('blog_reading') || 'null');
    if (r) {
      fontScale.value = r.s || 1;
      fontFamily.value = r.f === 'sans' ? 'sans' : 'serif';
      measureLevel.value = r.m || 'normal';
      ligatures.value = r.l !== false;
    }
  } catch {}
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('pagehide', savePosition);
  window.addEventListener('keydown', onKeydown);
  ro = new ResizeObserver(() => { measure(); onScroll(); });
  if (articleRef.value) ro.observe(articleRef.value);
  init();
});

onBeforeUnmount(() => {
  savePosition();
  window.removeEventListener('scroll', onScroll);
  window.removeEventListener('pagehide', savePosition);
  window.removeEventListener('keydown', onKeydown);
  ro?.disconnect();
  if (lightbox.value) unlockScroll();
});

const layoutName = computed(() => ({ standard: '特稿', wide: '图解', immersive: '沉浸', essay: '随笔', showcase: '陈列' } as Record<string, string>)[layout.value] || '特稿');
</script>

<template>
  <div v-if="post" class="post" :class="[`layout-${layout}`, `measure-${measureLevel}`]" :style="accentStyle">
    <!-- 阅读进度：顶端一笔墨 -->
    <div class="read-brush" aria-hidden="true">
      <span ref="brushRef">
        <svg viewBox="0 0 1000 6" preserveAspectRatio="none"><path d="M0 3.2 C 120 2.2 260 2.6 420 2.9 S 760 2.2 900 3 L 1000 3.4 L 1000 3.9 C 980 4.6 960 5.2 900 4.6 S 600 4.2 420 4.3 S 120 4.4 0 3.8 Z" /></svg>
      </span>
    </div>

    <!-- ============ 刊头 ============ -->
    <header class="post-head" data-shared-target>
      <!-- 沉浸：整屏水墨，标题压在画上；滚动时这一层像印好的纸一样被揭起 -->
      <div v-if="layout === 'immersive'" class="post-hero-art" aria-hidden="true">
        <InkCover :seed="post.slug" :no="post.number" :accent="post.accent_color" :variant="variant" :width="1600" :height="900" :intensity="1.9" />
      </div>

      <div class="page-shell post-head-inner">
        <div class="post-kicker">
          <span class="editorial-number">No. {{ no }}</span>
          <span class="post-kicker-line" aria-hidden="true" />
          <span class="post-kind">{{ layoutName }}</span>
          <NuxtLink v-for="t in post.tags" :key="t.slug" :to="`/tags/${t.slug}`" class="editorial-tag">{{ t.name }}</NuxtLink>
          <NuxtLink v-if="post.series" :to="`/series/${post.series.slug}`" class="post-series link-draw">
            {{ post.series.title }} · 第 {{ post.series.order || 1 }}{{ post.series.total ? ` / ${post.series.total}` : '' }} 篇
          </NuxtLink>
        </div>

        <h1 ref="titleRef" class="post-title">{{ post.title }}</h1>
        <p v-if="post.subtitle" v-reveal="160" class="post-subtitle reveal">{{ post.subtitle }}</p>

        <dl v-reveal="240" class="post-facts reveal">
          <div><dt>发布</dt><dd><time :datetime="post.published_at || undefined">{{ fmtDate(post.published_at) }}</time></dd></div>
          <div v-if="updatedLabel"><dt>修订</dt><dd>{{ updatedLabel }}</dd></div>
          <div><dt>篇幅</dt><dd>{{ post.word_count?.toLocaleString() }} 字</dd></div>
          <div><dt>阅读</dt><dd>约 {{ post.reading_minutes }} 分钟</dd></div>
          <div><dt>浏览</dt><dd>{{ post.view_count?.toLocaleString() }}</dd></div>
        </dl>
      </div>

      <!-- 标准 / 图解：标题下一条水墨长卷 -->
      <div v-if="layout === 'standard' || layout === 'wide'" v-reveal="120" class="post-scroll reveal" :class="{ 'is-bleed': layout === 'wide' }" aria-hidden="true">
        <InkCover :seed="post.slug" :no="post.number" :accent="post.accent_color" :variant="variant" :width="1600" :height="layout === 'wide' ? 560 : 440" />
      </div>
    </header>

    <ArticleChapterRail v-if="layout === 'showcase'" :toc="post.toc || []" :seed="post.slug" :accent="post.accent_color" />

    <!-- ============ 正文 ============ -->
    <div class="page-shell">
      <div class="post-grid">
        <div class="post-margin">
          <ArticleSidenotes v-if="layout !== 'essay'" :prose="proseRef" />
        </div>

        <div ref="articleRef" class="post-main">
          <div v-if="staleDays > 365" class="post-stale" role="note">
            <span class="post-stale-mark" aria-hidden="true">旧</span>
            本文最后修订于 {{ staleDays }} 天前，部分依赖或方案可能已经演进，请以最新官方文档为准。
          </div>

          <details v-if="post.toc?.length && layout !== 'essay'" class="toc-mobile">
            <summary>目录 · {{ post.toc.length }} 节</summary>
            <ArticleTocScale :toc="post.toc" />
          </details>

          <!-- eslint-disable-next-line vue/no-v-html -->
          <article
            ref="proseRef"
            class="article-prose"
            :class="{ 'prose-essay': layout === 'essay', 'font-sans-body': fontFamily === 'sans', 'no-ligatures': !ligatures }"
            :style="{ fontSize: `calc(var(--fs-body) * ${fontScale})` }"
            v-html="post.html"
          />

          <!-- 版权页 -->
          <section class="colophon" aria-labelledby="colophon-title">
            <p id="colophon-title" class="colophon-title">版权页 · Colophon</p>
            <dl class="colophon-grid">
              <div><dt>本期</dt><dd>No. {{ no }} · {{ layoutName }}</dd></div>
              <div><dt>篇幅</dt><dd>{{ post.word_count?.toLocaleString() }} 字 · 约 {{ post.reading_minutes }} 分钟</dd></div>
              <div><dt>首发</dt><dd>{{ fmtDate(post.published_at) }}</dd></div>
              <div><dt>修订</dt><dd>{{ updatedLabel || '未修订' }}</dd></div>
              <div><dt>设色</dt><dd><i class="colophon-swatch" aria-hidden="true" />{{ pigment.name }} · 头图「{{ variantName }}」</dd></div>
              <div><dt>授权</dt><dd><a href="https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans" target="_blank" rel="noopener" class="link-draw">CC BY-NC-SA 4.0</a>，转载请保留出处</dd></div>
            </dl>
            <span class="colophon-seal seal" aria-hidden="true">印</span>
          </section>
        </div>

        <aside ref="asideRef" class="post-aside toc-sidebar" :class="{ 'is-yielding': asideYield }" aria-label="目录与阅读设置">
          <div class="post-aside-sticky">
            <ArticleTocScale v-if="layout !== 'essay'" :toc="post.toc || []" />
            <div class="reading-tools">
              <div class="reading-progress">
                <p class="eyebrow">已读</p>
                <p class="reading-pct"><span ref="percentRef">00</span><small>%</small></p>
              </div>
              <p class="eyebrow">阅读设置</p>
              <div class="reading-tools-row">
                <div class="stepper">
                  <button type="button" class="tool-btn" aria-label="缩小字号" :disabled="fontScale <= 0.9" @click="setScale(-0.05)">A<sup>−</sup></button>
                  <span class="tool-value">{{ Math.round(fontScale * 100) }}</span>
                  <button type="button" class="tool-btn" aria-label="放大字号" :disabled="fontScale >= 1.2" @click="setScale(0.05)">A<sup>+</sup></button>
                </div>
                <UiSegmented :model-value="fontFamily" :options="familyOptions" size="sm" aria-label="正文字体" @update:model-value="setFamily" />
              </div>
              <div class="reading-tools-row">
                <span class="tool-label">行宽</span>
                <UiSegmented :model-value="measureLevel" :options="measureOptions" size="sm" aria-label="行宽" @update:model-value="setMeasure" />
              </div>
              <button type="button" class="tool-toggle" :aria-pressed="ligatures" @click="toggleLigatures">
                <span>代码连字</span><i aria-hidden="true" />
              </button>
            </div>
          </div>
        </aside>
      </div>

      <!-- ============ 文末 ============ -->
      <footer class="post-end">
        <div class="post-actions article-actions">
          <ArticleLikeSeal :slug="post.slug" :liked="!!post.liked" :count="post.like_count || 0" @announce="announce" />
          <button type="button" class="action-btn" @click="share">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" /><path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" /></svg>
            <span>{{ shared ? '链接已复制' : '分享本期' }}</span>
          </button>
        </div>

        <nav v-if="post.prev || post.next" class="post-pager" aria-label="上一篇与下一篇">
          <NuxtLink v-if="post.prev" :to="`/posts/${post.prev.slug}`" class="pager-card" data-cursor="read">
            <span class="eyebrow"><i class="pager-arrow" aria-hidden="true">←</i> 上一篇</span>
            <span class="pager-title">{{ post.prev.title }}</span>
          </NuxtLink>
          <span v-else />
          <NuxtLink v-if="post.next" :to="`/posts/${post.next.slug}`" class="pager-card is-next" data-cursor="read">
            <span class="pager-art" aria-hidden="true"><InkCover :seed="post.next.slug" :width="400" :height="200" :numeral="false" :seal="false" /></span>
            <span class="eyebrow">下一篇 <i class="pager-arrow" aria-hidden="true">→</i></span>
            <span class="pager-title">{{ post.next.title }}</span>
          </NuxtLink>
        </nav>

        <section v-if="related.length" class="post-related" aria-labelledby="related-title">
          <h2 id="related-title" class="eyebrow">相关阅读</h2>
          <div class="related-list">
            <NuxtLink v-for="r in related" :key="r.id" :to="`/posts/${r.slug}`" class="related-item register-focus" data-cursor="read">
              <span class="related-art" aria-hidden="true"><InkCover :seed="r.slug" :no="r.number" :width="160" :height="100" :numeral="false" :seal="false" /></span>
              <span class="editorial-number">No. {{ String(r.number || 0).padStart(3, '0') }}</span>
              <span class="related-title">{{ r.title }}</span>
            </NuxtLink>
          </div>
        </section>

        <ArticleCommentSection v-if="post.allow_comments !== false" :post-slug="post.slug" />
      </footer>
    </div>

    <!-- 窄屏的阅读设置入口 -->
    <button type="button" class="settings-fab" :aria-expanded="settingsOpen" aria-label="阅读设置" @click="settingsOpen = !settingsOpen">Aa</button>
    <Transition name="sheet">
      <div v-if="settingsOpen" class="settings-sheet" role="dialog" aria-label="阅读设置">
        <div class="settings-row">
          <span class="tool-label">字号</span>
          <div class="stepper">
            <button type="button" class="tool-btn" aria-label="缩小字号" :disabled="fontScale <= 0.9" @click="setScale(-0.05)">A<sup>−</sup></button>
            <span class="tool-value">{{ Math.round(fontScale * 100) }}</span>
            <button type="button" class="tool-btn" aria-label="放大字号" :disabled="fontScale >= 1.2" @click="setScale(0.05)">A<sup>+</sup></button>
          </div>
        </div>
        <div class="settings-row"><span class="tool-label">字体</span><UiSegmented :model-value="fontFamily" :options="familyOptions" size="sm" aria-label="正文字体" @update:model-value="setFamily" /></div>
        <div class="settings-row"><span class="tool-label">行宽</span><UiSegmented :model-value="measureLevel" :options="measureOptions" size="sm" aria-label="行宽" @update:model-value="setMeasure" /></div>
        <button type="button" class="tool-toggle" :aria-pressed="ligatures" @click="toggleLigatures"><span>代码连字</span><i aria-hidden="true" /></button>
      </div>
    </Transition>

    <!-- 继续阅读 -->
    <Transition name="toast">
      <div v-if="resumeAt > 0" class="resume-toast" role="status">
        <span>上次读到 {{ Math.round(resumeAt * 100) }}%</span>
        <button type="button" class="btn btn-sm btn-solid" @click="resume">继续阅读</button>
        <button type="button" class="resume-close" aria-label="关闭" @click="resumeAt = 0">×</button>
      </div>
    </Transition>

    <p class="sr-only" aria-live="polite">{{ announcement }}</p>

    <!-- 图片灯箱 -->
    <Teleport to="body">
      <div
        v-if="lightbox"
        class="lightbox"
        role="dialog"
        aria-modal="true"
        :aria-label="lightbox.alt || '查看大图'"
        data-lenis-prevent
        @click="onLbClick"
        @wheel="onLbWheel"
        @pointerdown="onLbDown"
        @pointermove="onLbMove"
        @pointerup="onLbUp"
        @pointercancel="onLbUp"
      >
        <img ref="lightboxImg" :src="lightbox.src" :alt="lightbox.alt" draggable="false">
        <p class="lightbox-caption">
          <span v-if="imageCount > 1">{{ lightbox.index + 1 }} / {{ imageCount }}</span>
          {{ lightbox.alt }}
          <span class="lightbox-hint">滚轮或双指缩放 · Esc 关闭</span>
        </p>
        <button v-if="imageCount > 1" type="button" class="lightbox-nav is-prev" aria-label="上一张" @click.stop="step(-1)">←</button>
        <button v-if="imageCount > 1" type="button" class="lightbox-nav is-next" aria-label="下一张" @click.stop="step(1)">→</button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* 设色：文章强调色映射到传统颜料；夜间换同色相的亮版本 */
.post { --color-accent: var(--post-accent); --color-accent-text: var(--post-accent-text); }
:global(html[data-theme="dark"]) .post { --color-accent: var(--post-accent-night); --color-accent-text: var(--post-accent-night); }

/* ---------------- 阅读进度：一笔墨 ---------------- */
.read-brush {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 6px;
  z-index: calc(var(--z-header) + 1);
  overflow: hidden;
  pointer-events: none;
}
.read-brush span { display: block; height: 100%; transform: translate3d(-100%, 0, 0); will-change: transform; }
.read-brush svg { width: 100%; height: 100%; display: block; }
.read-brush path { fill: var(--color-ink); opacity: 0.85; }

/* ---------------- 刊头 ---------------- */
.post-head { position: relative; padding-block: clamp(48px, 8vw, 112px) 0; }
.post-head-inner { position: relative; z-index: 1; }
.post-kicker { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.post-kicker-line { width: 40px; height: 1px; background: var(--color-line-strong); }
.post-kind { font-family: var(--font-mono); font-size: var(--fs-nano); letter-spacing: 0.16em; color: var(--color-ink-muted); margin-right: 6px; }
.post-series { font-size: var(--fs-micro); color: var(--color-accent-text); margin-left: 6px; }
.post-title {
  max-width: 17em;
  margin-top: 28px;
  font-family: var(--font-serif);
  font-size: clamp(36px, 5.6vw, 88px);
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: -0.025em;
  text-wrap: balance;
}
.post-subtitle {
  max-width: 36em;
  margin-top: 22px;
  font-family: var(--font-serif);
  font-size: clamp(18px, 1.7vw, 24px);
  line-height: 1.6;
  color: var(--color-ink-muted);
}
.post-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 40px;
  margin-top: 44px;
  padding-top: 20px;
  border-top: 1px solid var(--color-line);
}
.post-facts div { display: flex; flex-direction: column; gap: 4px; }
.post-facts dt { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-ink-muted); }
.post-facts dd { font-size: var(--fs-small); font-variant-numeric: tabular-nums; }

/* 标准 / 图解：标题跨 1–10 栏，元信息竖排在 11–12 栏 */
@media (min-width: 1100px) {
  .layout-standard .post-head-inner,
  .layout-wide .post-head-inner {
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    column-gap: var(--gutter);
  }
  .layout-standard .post-kicker,
  .layout-standard .post-title,
  .layout-standard .post-subtitle,
  .layout-wide .post-kicker,
  .layout-wide .post-title,
  .layout-wide .post-subtitle { grid-column: 1 / 11; }
  .layout-standard .post-facts,
  .layout-wide .post-facts {
    grid-column: 11 / 13;
    grid-row: 1 / 4;
    align-self: end;
    justify-self: end;
    flex-wrap: nowrap;
    gap: 22px;
    margin: 0;
    padding: 0 0 0 22px;
    border-top: 0;
    border-left: 1px solid var(--color-line);
    writing-mode: vertical-rl;
  }
  .layout-standard .post-facts dd,
  .layout-wide .post-facts dd { white-space: nowrap; }
  .layout-standard .post-facts div,
  .layout-wide .post-facts div { flex-direction: row; gap: 10px; }
  .layout-standard .post-facts dt,
  .layout-wide .post-facts dt { letter-spacing: 0.3em; }
}

/* 水墨长卷 */
.post-scroll {
  position: relative;
  margin: clamp(40px, 5vw, 72px) auto 0;
  width: calc(100% - 2 * var(--page-padding));
  max-width: calc(var(--full-max-width) - 2 * var(--page-padding));
  aspect-ratio: 1600 / 440;
  border-block: 1px solid var(--color-line);
  overflow: hidden;
}
.post-scroll.is-bleed { width: 100%; max-width: none; aspect-ratio: 1600 / 560; }

/* 沉浸：整屏水墨 + 揭版 */
.layout-immersive .post-head {
  min-height: calc(100svh - var(--header-h));
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding-bottom: clamp(40px, 6vw, 80px);
  overflow: clip;
}
.post-hero-art { position: absolute; inset: 0; }
.post-hero-art::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, var(--color-bg) 4%, color-mix(in oklab, var(--color-bg) 55%, transparent) 30%, transparent 55%);
}
@supports (animation-timeline: view()) {
  html.motion-ready .layout-immersive .post-hero-art {
    animation: lift-off linear both;
    animation-timeline: view();
    animation-range: exit 0% exit 100%;
  }
}
@keyframes lift-off {
  to { transform: translate3d(0, -18%, 0) scale(1.08); opacity: 0.2; }
}
.layout-immersive .post-title { font-size: clamp(40px, 6.4vw, 104px); max-width: 15em; }

/* 随笔：没有头图，窄栏居中，安静 */
.layout-essay .post-head-inner { max-width: 760px; text-align: center; }
.layout-essay .post-kicker { justify-content: center; }
.layout-essay .post-title { margin-inline: auto; font-size: clamp(34px, 4.6vw, 64px); }
.layout-essay .post-subtitle { margin-inline: auto; }
.layout-essay .post-facts { justify-content: center; }
.layout-essay .post-head-inner::after {
  content: "";
  display: block;
  width: 1px;
  height: 72px;
  margin: 48px auto 0;
  background: linear-gradient(var(--color-ink), transparent);
}

/* ---------------- 正文网格：页边旁注 | 正文 | 目录 ---------------- */
.post-grid {
  display: grid;
  grid-template-columns: minmax(150px, 220px) minmax(0, var(--measure, 680px)) minmax(180px, 230px);
  justify-content: center;
  gap: clamp(32px, 4vw, 72px);
  padding-top: clamp(48px, 6vw, 96px);
}
.measure-narrow { --measure: 600px; }
.measure-wide { --measure: 780px; }
.layout-wide { --measure: 720px; }
.layout-essay { --measure: 620px; }
.post-main { min-width: 0; }
.post-margin { position: relative; }
.post-aside { position: relative; }
.post-aside-sticky {
  position: sticky;
  top: calc(var(--header-h) + 32px);
  max-height: calc(100vh - var(--header-h) - 64px);
  overflow-y: auto;
  scrollbar-width: none;
}
.post-aside-sticky::-webkit-scrollbar { display: none; }
.post-aside-sticky { transition: opacity var(--dur-sm) var(--ease-out-quart), visibility 0s linear 0s; }
.post-aside.is-yielding .post-aside-sticky {
  opacity: 0;
  visibility: hidden;
  transition: opacity var(--dur-sm) var(--ease-out-quart), visibility 0s linear var(--dur-sm);
}

/* 图解：代码与表格破栏到 1080（以正文为中心；两栏时正文不居中，放不下，留在栏内） */
.layout-wide .article-prose :deep(> .code-block),
.layout-wide .article-prose :deep(> .code-group),
.layout-wide .article-prose :deep(> .table-wrap) {
  width: min(1080px, 100vw - 2 * var(--page-padding));
  margin-inline: calc(50% - min(1080px, 100vw - 2 * var(--page-padding)) / 2);
}

.reading-tools { margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--color-line); display: flex; flex-direction: column; gap: 12px; }
.reading-progress { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
.reading-pct {
  font-family: var(--font-display);
  font-size: 30px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums lining-nums;
}
.reading-pct small { margin-left: 2px; font-size: 13px; color: var(--color-ink-muted); }
.reading-tools-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.tool-label { font-size: var(--fs-micro); color: var(--color-ink-muted); }
.stepper {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
}
.tool-btn {
  height: 26px;
  min-width: 30px;
  padding: 0 8px;
  border-radius: var(--radius-pill);
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-muted);
  transition: color var(--dur-micro) ease, background-color var(--dur-micro) ease, transform 400ms var(--ease-spring);
}
.tool-btn sup { font-family: var(--font-mono); font-size: 9px; font-weight: 400; }
.tool-btn:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 6%, transparent); }
.tool-btn:active { transform: scale(0.9); }
.tool-btn[disabled] { opacity: 0.35; pointer-events: none; }
.tool-value { min-width: 30px; text-align: center; font-family: var(--font-mono); font-size: 11px; color: var(--color-ink-muted); font-variant-numeric: tabular-nums; }
.tool-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
}
.tool-toggle i { position: relative; width: 28px; height: 16px; border-radius: 99px; border: 1px solid var(--color-line-strong); transition: background-color var(--dur-sm) ease, border-color var(--dur-sm) ease; }
.tool-toggle i::after { content: ""; position: absolute; top: 2px; left: 2px; width: 10px; height: 10px; border-radius: 50%; background: var(--color-ink-muted); transition: transform 400ms var(--ease-spring), background-color var(--dur-sm) ease; }
.tool-toggle[aria-pressed="true"] i { background: var(--color-ink); border-color: var(--color-ink); }
.tool-toggle[aria-pressed="true"] i::after { transform: translateX(12px); background: var(--color-bg); }

.post-stale {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 32px;
  padding: 14px 18px;
  border: 1px solid var(--color-line);
  background: color-mix(in oklab, var(--color-warn) 7%, transparent);
  font-size: var(--fs-small);
  line-height: 1.7;
  color: var(--color-ink-muted);
}
.post-stale-mark { flex-shrink: 0; display: grid; place-items: center; width: 26px; height: 26px; font-family: var(--font-serif); font-weight: 900; color: var(--color-bg); background: var(--color-ink-muted); border-radius: 2px; }

.toc-mobile { display: none; margin-bottom: 32px; border-block: 1px solid var(--color-line); }
.toc-mobile summary { padding: 12px 0; font-size: var(--fs-small); cursor: pointer; list-style: none; }
.toc-mobile summary::-webkit-details-marker { display: none; }
.toc-mobile[open] summary { border-bottom: 1px solid var(--color-line); }
.toc-mobile :deep(.toc) { padding: 12px 0 16px; }
.toc-mobile :deep(.toc-title) { display: none; }

@media (max-width: 1279px) {
  .post-grid { grid-template-columns: minmax(0, var(--measure, 680px)) minmax(180px, 220px); }
  .post-margin { display: none; }
}
@media (min-width: 1081px) and (max-width: 1279px) {
  .layout-wide .article-prose :deep(> .code-block),
  .layout-wide .article-prose :deep(> .code-group),
  .layout-wide .article-prose :deep(> .table-wrap) { width: auto; margin-inline: 0; }
}
@media (max-width: 1080px) {
  .post-grid { grid-template-columns: minmax(0, var(--measure, 680px)); }
  .post-aside { display: none; }
  .toc-mobile { display: block; }
}

/* ---------------- 版权页 ---------------- */
.colophon {
  position: relative;
  margin-top: 4em;
  padding: 28px 0 8px;
  border-top: 1px solid var(--color-ink);
}
.colophon-title { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-ink-muted); }
.colophon-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 32px; margin-top: 20px; }
.colophon-grid div { display: grid; grid-template-columns: 3.4em 1fr; gap: 10px; align-items: baseline; padding-bottom: 12px; border-bottom: 1px solid var(--color-line); }
.colophon-grid dt { font-family: var(--font-serif); font-size: 13px; font-weight: 700; color: var(--color-ink-muted); }
.colophon-grid dd { font-size: var(--fs-small); font-variant-numeric: tabular-nums; }
.colophon-swatch { display: inline-block; width: 10px; height: 10px; margin-right: 8px; border-radius: 50%; background: var(--color-accent); }
.colophon-seal { position: absolute; right: 0; top: 18px; font-size: 13px; color: var(--color-seal); transform: rotate(-6deg); }
@media (max-width: 640px) { .colophon-grid { grid-template-columns: 1fr; } }

/* ---------------- 文末：与正文左缘对齐（B43） ---------------- */
.post-end { max-width: calc(var(--measure, 680px) + 240px); margin: clamp(64px, 8vw, 112px) auto 0; }
.post-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding-block: 28px;
  border-block: 1px solid var(--color-line);
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 64px;
  padding: 0 22px;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-xs);
  font-size: var(--fs-small);
  transition: color var(--dur-micro) ease, border-color var(--dur-micro) ease, transform var(--dur-impress) var(--ease-impress);
}
.action-btn:hover { border-color: var(--color-ink); }
.action-btn:active { transform: scale(0.98); }

.post-pager { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin-top: 48px; background: var(--color-line); border: 1px solid var(--color-line); }
.pager-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 180px;
  padding: 28px 32px;
  background: var(--color-bg);
  overflow: hidden;
}
.pager-card.is-next { text-align: right; align-items: flex-end; }
.pager-art { position: absolute; inset: 0; opacity: 0; transition: opacity 900ms var(--ease-out-quart); pointer-events: none; }
.pager-card.is-next:hover .pager-art { opacity: 0.35; }
.pager-card > :not(.pager-art) { position: relative; }
.pager-card .eyebrow { display: inline-flex; align-items: center; gap: 8px; }
.pager-arrow { display: inline-block; font-style: normal; color: var(--color-accent-text); transition: transform 600ms var(--ease-out-expo); }
.pager-card:hover .pager-arrow { transform: translateX(-5px); }
.pager-card.is-next:hover .pager-arrow { transform: translateX(5px); }
.pager-title {
  max-width: 20em;
  font-family: var(--font-serif);
  font-size: clamp(18px, 1.8vw, 24px);
  font-weight: 700;
  line-height: 1.45;
  transition: transform 700ms var(--ease-out-expo);
}
.pager-card:hover .pager-title { transform: translateX(4px); }
.pager-card.is-next:hover .pager-title { transform: translateX(-4px); }
.post-pager > span { background: var(--color-bg); }

.post-related { margin-top: 64px; }
.related-list { margin-top: 16px; border-top: 1px solid var(--color-ink); }
.related-item {
  position: relative;
  display: grid;
  grid-template-columns: 96px 88px 1fr;
  align-items: center;
  gap: 18px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-line);
}
.related-art { display: block; width: 96px; height: 60px; overflow: hidden; border: 1px solid var(--color-line); }
.related-item::after {
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
.related-item:hover::after { transform: scaleX(1); transform-origin: 0 50%; }
.related-title { font-family: var(--font-serif); font-size: 18px; font-weight: 600; transition: transform 700ms var(--ease-out-expo); }
.related-item:hover .related-title { transform: translateX(6px); }

@media (max-width: 640px) {
  .post-pager { grid-template-columns: 1fr; }
  .related-item { grid-template-columns: 72px 1fr; }
  .related-item .editorial-number { display: none; }
  .related-art { width: 72px; height: 46px; }
}

/* ---------------- 阅读设置（窄屏） ---------------- */
.settings-fab {
  position: fixed;
  right: 16px;
  bottom: calc(16px + env(safe-area-inset-bottom));
  z-index: var(--z-overlay);
  display: none;
  width: 48px;
  height: 48px;
  place-items: center;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-paper-glass);
  border: 1px solid var(--color-line-strong);
  border-radius: 50%;
  box-shadow: var(--shadow-md);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
}
.settings-sheet {
  position: fixed;
  right: 16px;
  bottom: calc(76px + env(safe-area-inset-bottom));
  z-index: var(--z-overlay);
  width: min(320px, calc(100vw - 32px));
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  background: var(--color-bg);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-float);
}
.settings-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
@media (max-width: 1080px) { .settings-fab { display: grid; } }
.sheet-enter-active { transition: opacity 260ms var(--ease-out-quart), transform 500ms var(--ease-out-expo); }
.sheet-leave-active { transition: opacity 160ms var(--ease-in-quart), transform 200ms var(--ease-in-quart); }
.sheet-enter-from, .sheet-leave-to { opacity: 0; transform: translate3d(0, 12px, 0) scale(0.97); transform-origin: 100% 100%; }

/* ---------------- 浮层 ---------------- */
.resume-toast {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: var(--z-overlay);
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 8px 8px 18px;
  transform: translateX(-50%);
  background: var(--color-paper-glass);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  box-shadow: var(--shadow-float);
  -webkit-backdrop-filter: blur(16px) saturate(1.5);
  backdrop-filter: blur(16px) saturate(1.5);
  font-size: var(--fs-small);
}
.resume-toast > span { white-space: nowrap; }
.resume-close { width: 28px; height: 28px; border-radius: 50%; color: var(--color-ink-muted); font-size: 18px; }
.resume-close:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 6%, transparent); }
@media (max-width: 480px) {
  .resume-toast { gap: 10px; padding-left: 14px; font-size: var(--fs-micro); }
}
.toast-enter-active { transition: opacity 400ms ease, transform 700ms var(--ease-spring); transition-delay: 600ms; }
.toast-leave-active { transition: opacity 240ms ease, transform 300ms var(--ease-in-quart); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 20px) scale(0.96); }

.lightbox {
  position: fixed;
  inset: 0;
  z-index: var(--z-overlay);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 5vh 5vw;
  background: color-mix(in oklab, var(--color-bg) 94%, transparent);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  touch-action: none;
  animation: fade-in 360ms var(--ease-out-quart);
}
.lightbox img { max-width: 100%; max-height: 82vh; object-fit: contain; will-change: transform; box-shadow: var(--shadow-float); user-select: none; }
.lightbox-caption { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 14px; font-size: var(--fs-micro); color: var(--color-ink-muted); }
.lightbox-hint { font-family: var(--font-mono); color: var(--color-ink-faint); }
.lightbox-nav {
  position: absolute;
  top: 50%;
  width: 48px;
  height: 48px;
  margin-top: -24px;
  font-size: 18px;
  border: 1px solid var(--color-line-strong);
  border-radius: 50%;
  background: var(--color-bg);
}
.lightbox-nav.is-prev { left: 24px; }
.lightbox-nav.is-next { right: 24px; }
@keyframes fade-in { from { opacity: 0; } }
</style>
