<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';
import { frameLerp } from '~/composables/motion/tokens';

/**
 * 首页 · 墨池上的纸笺（PRD 5.1 · docs/design-v2.md）
 *
 * 一方墨池（<InkPond>，实时流体）铺在最底层，文章、项目、TIL 是浮在上面的纸笺。
 * - 平移状态是普通变量，不进 Vue 响应式；每帧只由 gsap.ticker 写一次 transform
 * - 无限循环：卡片按世界尺寸取模摆放。所有卡片同一景深，彼此的相对位置永远不变（B37：不再漂移、重叠）
 * - 视差只给中央标题（水印式反向位移）与墨池（墨不随纸笺移动）
 * - 拖拽时纸面按速度轻微缩放与透视倾斜；松手后惯性滑行（按真实时间步长）
 * - 筛选：被筛掉的纸笺沉下去，留下的纸笺补间到新的紧凑布局（FLIP 思路，位置由同一个 ticker 写）
 * - 没有无因果的空闲漂移；画布动不动，只取决于读者
 */

export interface CanvasItem {
  key: string;
  kind: 'post' | 'project' | 'til';
  href: string;
  title: string;
  excerpt?: string;
  number?: number | null;
  meta?: string;
  tags?: string[];
  accent?: string | null;
  lang?: string | null;
  langColor?: string | null;
  stars?: number | null;
  layout?: string | null;
  slug?: string;
}

const props = defineProps<{ items: CanvasItem[]; filter: 'all' | 'post' | 'project' | 'til' }>();

const viewportRef = ref<HTMLElement | null>(null);
const surfaceRef = ref<HTMLElement | null>(null);
const titleRef = ref<HTMLElement | null>(null);
const titleAccentRef = ref<HTMLElement | null>(null);
const coordsRef = ref<HTMLElement | null>(null);
const miniRef = ref<SVGRectElement | null>(null);
const isDragging = ref(false);
const entering = ref(true);
const withIntro = ref(false);

const CELL_W = 360;
const CELL_H = 420;
const CARD_SIZE: Record<CanvasItem['kind'], [number, number]> = { post: [288, 330], project: [260, 220], til: [236, 200] };
/** 世界中心的标题留白区（半宽 / 半高），初始视图正好以它为中心 */
const CLEAR_HW = 460;
const CLEAR_HH = 200;

function rand(seed: number) {
  const x = Math.sin(seed * 9301 + 49297) * 233280;
  return x - Math.floor(x);
}

interface Placed { item: CanvasItem; x: number; y: number; tilt: number; delay: number }

/** 给定一组条目，生成错落的网格布局；跳过会压住中央标题的格子 */
function buildLayout(items: CanvasItem[]) {
  const n = Math.max(items.length, 1);
  const cols = Math.max(6, Math.ceil(Math.sqrt(n * 1.6)));
  let rows = Math.max(4, Math.ceil(n / cols) + 1);
  for (;;) {
    const worldW = cols * CELL_W;
    const worldH = rows * CELL_H;
    const cx = worldW / 2;
    const cy = worldH / 2;
    const cells: Array<{ c: number; r: number }> = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push({ c, r });
    // 由近及远：离中心近的格子先用，筛选后留下的纸笺会聚拢到标题周围
    cells.sort((a, b) => {
      const da = Math.hypot((a.c + 0.5) * CELL_W - cx, ((a.r + 0.5) * CELL_H - cy) * 1.4) + rand(a.c * 31 + a.r * 17) * 260;
      const db = Math.hypot((b.c + 0.5) * CELL_W - cx, ((b.r + 0.5) * CELL_H - cy) * 1.4) + rand(b.c * 31 + b.r * 17) * 260;
      return da - db;
    });
    const placed: Placed[] = [];
    let k = 0;
    for (let i = 0; i < items.length && k < cells.length; i++) {
      const item = items[i];
      const [w, h] = CARD_SIZE[item.kind];
      const seed = item.key.length * 7 + i;
      const jx = (rand(seed * 7 + 3) - 0.5) * 70;
      const jy = (rand(seed * 13 + 5) - 0.5) * 90;
      let x = 0;
      let y = 0;
      for (; k < cells.length; k++) {
        x = cells[k].c * CELL_W + (CELL_W - w) / 2 + jx;
        y = cells[k].r * CELL_H + (CELL_H - h) / 2 + jy;
        const hitsTitle = x < cx + CLEAR_HW && x + w > cx - CLEAR_HW && y < cy + CLEAR_HH && y + h > cy - CLEAR_HH;
        if (!hitsTitle) break;
      }
      if (k >= cells.length) break;
      k++;
      const dist = Math.hypot(x + w / 2 - cx, y + h / 2 - cy);
      placed.push({ item, x, y, tilt: (rand(seed * 23 + 7) - 0.5) * 3, delay: Math.min(0.7, dist / 2200) });
    }
    if (placed.length >= items.length || rows > 40) return { worldW, worldH, placed };
    rows += 1;
  }
}

/** 世界尺寸始终按全部条目计算，筛选只改变位置，不改变循环周期 */
const world = computed(() => buildLayout(props.items));
const layout = computed(() => world.value.placed);

/* ------------------------------------------------------------------ */
/* 运动状态（非响应式）                                                */
/* ------------------------------------------------------------------ */
let panX = 0;
let panY = 0;
let velX = 0;
let velY = 0;
let lastMoveTime = 0;
let pointerId: number | null = null;
let startX = 0;
let startY = 0;
let lastX = 0;
let lastY = 0;
let moved = 0;
let vw = 0;
let vh = 0;
let cardEls: HTMLElement[] = [];
let offscreen: boolean[] = [];
/** 每张纸笺当前的世界坐标（筛选重排时补间） */
let pos: Array<{ x: number; y: number }> = [];
let tickerFn: ((time: number, delta: number) => void) | null = null;
let ro: ResizeObserver | null = null;
let io: IntersectionObserver | null = null;
let inView = true;
let tiltX = 0;
let tiltY = 0;
let scale = 1;
let initialPanX = 0;
let initialPanY = 0;
let coordsText = '';

function mod(a: number, n: number) {
  return ((a % n) + n) % n;
}

function render() {
  const { worldW, worldH } = world.value;
  const placed = layout.value;
  const marginX = CELL_W;
  const marginY = CELL_H;
  for (let i = 0; i < placed.length; i++) {
    const el = cardEls[i];
    const p = pos[i];
    if (!el || !p) continue;
    const x = mod(p.x + panX + marginX, worldW) - marginX;
    const y = mod(p.y + panY + marginY, worldH) - marginY;
    const out = x > vw + 40 || y > vh + 40 || x < -CELL_W || y < -CELL_H;
    if (out !== offscreen[i]) {
      offscreen[i] = out;
      el.style.visibility = out ? 'hidden' : '';
    }
    if (!out) el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) rotate(${placed[i].tilt}deg)`;
  }
  const relX = panX - initialPanX;
  const relY = panY - initialPanY;
  // 标题像水印一样轻微反向位移
  if (titleRef.value) {
    const tx = Math.max(-60, Math.min(60, -relX * 0.03));
    const ty = Math.max(-40, Math.min(40, -relY * 0.03));
    const t = `translate3d(${tx.toFixed(1)}px, ${ty.toFixed(1)}px, 0)`;
    titleRef.value.style.transform = t;
    if (titleAccentRef.value) titleAccentRef.value.style.transform = t;
  }
  if (surfaceRef.value) {
    surfaceRef.value.style.transform = `perspective(1400px) rotateX(${tiltX.toFixed(3)}deg) rotateY(${tiltY.toFixed(3)}deg) scale(${scale.toFixed(4)})`;
  }
  if (coordsRef.value) {
    const fmt = (v: number) => {
      const r = Math.round(v);
      return `${r >= 0 ? '+' : '−'}${String(Math.abs(r)).padStart(4, '0')}`;
    };
    const text = `X ${fmt(-relX)}  Y ${fmt(relY)}`;
    if (text !== coordsText) {
      coordsText = text;
      coordsRef.value.textContent = text;
    }
  }
  if (miniRef.value) {
    const mx = mod(-relX + worldW / 2 - vw / 2, worldW) / worldW;
    const my = mod(-relY + worldH / 2 - vh / 2, worldH) / worldH;
    miniRef.value.setAttribute('x', (mx * 100).toFixed(2));
    miniRef.value.setAttribute('y', (my * 100 * (worldH / worldW)).toFixed(2));
  }
}

function measure() {
  const el = viewportRef.value;
  if (!el) return;
  vw = el.clientWidth;
  vh = el.clientHeight;
}

function centerView() {
  measure();
  const { worldW, worldH } = world.value;
  initialPanX = vw / 2 - worldW / 2;
  initialPanY = vh / 2 - worldH / 2;
}

function tick(_time: number, deltaMs: number) {
  if (!inView) return;
  const dt = Math.min(deltaMs, 50) / 16.667;
  if (pointerId === null) {
    // 惯性滑行：时间无关的摩擦
    const friction = Math.pow(0.93, dt);
    velX *= friction;
    velY *= friction;
    if (Math.abs(velX) < 0.01) velX = 0;
    if (Math.abs(velY) < 0.01) velY = 0;
    panX += velX * dt;
    panY += velY * dt;
  } else if (performance.now() - lastMoveTime > 80) {
    velX *= Math.pow(0.8, dt);
    velY *= Math.pow(0.8, dt);
  }
  // 纸面随速度轻微倾斜与收缩，停下后回正
  const speed = Math.min(Math.hypot(velX, velY), 60);
  const k = frameLerp(0.12, deltaMs);
  tiltX += (Math.max(-4, Math.min(4, velY * 0.12)) - tiltX) * k;
  tiltY += (Math.max(-4, Math.min(4, -velX * 0.12)) - tiltY) * k;
  scale += (1 - speed / 1100 - scale) * k;
  render();
}

/* ------------------------------------------------------------------ */
/* 交互                                                                */
/* ------------------------------------------------------------------ */
function onPointerDown(e: PointerEvent) {
  if (e.button !== 0) return;
  pointerId = e.pointerId;
  startX = lastX = e.clientX;
  startY = lastY = e.clientY;
  moved = 0;
  velX = velY = 0;
  lastMoveTime = performance.now();
  // 不能立刻 setPointerCapture：捕获后 click 会派发到视口而不是卡片链接，单纯的点击就打不开文章。
}

function onPointerMove(e: PointerEvent) {
  if (e.pointerId !== pointerId) return;
  const dx = e.clientX - lastX;
  const dy = e.clientY - lastY;
  lastX = e.clientX;
  lastY = e.clientY;
  moved = Math.max(moved, Math.hypot(e.clientX - startX, e.clientY - startY));
  if (moved > 4 && !isDragging.value) {
    isDragging.value = true;
    viewportRef.value?.setPointerCapture?.(e.pointerId);
  }
  panX += dx;
  panY += dy;
  velX = velX * 0.5 + dx * 0.5;
  velY = velY * 0.5 + dy * 0.5;
  lastMoveTime = performance.now();
}

function onPointerUp(e: PointerEvent) {
  if (e.pointerId !== pointerId) return;
  pointerId = null;
  if (viewportRef.value?.hasPointerCapture?.(e.pointerId)) viewportRef.value.releasePointerCapture(e.pointerId);
  gsap.delayedCall(0, () => { isDragging.value = false; });
}

/** 拖拽后松手不触发卡片链接 */
function onClickCapture(e: MouseEvent) {
  if (moved > 6) {
    e.preventDefault();
    e.stopPropagation();
  }
  moved = 0;
}

/** 滚轮与触控板：横向（或按住 Shift）平移画布；纵向留给页面滚动 */
function onWheel(e: WheelEvent) {
  const horizontal = Math.abs(e.deltaX) > Math.abs(e.deltaY) * 0.6;
  if (horizontal || e.shiftKey) {
    e.preventDefault();
    const dx = e.shiftKey && !e.deltaX ? e.deltaY : e.deltaX;
    velX = -dx * 0.32;
    if (horizontal) velY = -e.deltaY * 0.32;
  }
}

function nudge(dx: number, dy: number) {
  const state = { x: panX, y: panY };
  velX = velY = 0;
  gsap.to(state, {
    x: panX + dx,
    y: panY + dy,
    duration: 0.7,
    ease: 'outExpo',
    overwrite: true,
    onUpdate: () => { panX = state.x; panY = state.y; },
  });
}

function resetView() {
  nudge(initialPanX - panX, initialPanY - panY);
}

function onKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  if (!inView) return;
  const step = 240;
  if (e.key === '0') resetView();
  else if (e.key === 'ArrowLeft') { e.preventDefault(); nudge(step, 0); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); nudge(-step, 0); }
  else if (e.key === 'ArrowUp' && window.scrollY < 40) { e.preventDefault(); nudge(0, step); }
  else if (e.key === 'ArrowDown' && window.scrollY < 40) { e.preventDefault(); nudge(0, -step); }
}

/** 键盘 Tab 聚焦到卡片时，把它平移到视口中央 */
function onFocusIn(e: FocusEvent) {
  const card = (e.target as HTMLElement).closest<HTMLElement>('.canvas-card');
  if (!card || pointerId !== null) return;
  const r = card.getBoundingClientRect();
  const v = viewportRef.value!.getBoundingClientRect();
  nudge(v.left + v.width / 2 - (r.left + r.width / 2), v.top + v.height / 2 - (r.top + r.height / 2));
}

function collectCards() {
  cardEls = Array.from(surfaceRef.value?.querySelectorAll<HTMLElement>('.canvas-card') || []);
  offscreen = cardEls.map(() => false);
  pos = layout.value.map((p) => ({ x: p.x, y: p.y }));
}

/* ---- 筛选：留下的纸笺补间到新的紧凑布局 ---- */
watch(() => props.filter, (f) => {
  const placed = layout.value;
  if (f === 'all') {
    placed.forEach((p, i) => pos[i] && gsap.to(pos[i], { x: p.x, y: p.y, duration: 1, ease: 'outExpo', delay: Math.min(i, 8) * 0.02, overwrite: true }));
    return;
  }
  const sub = buildLayout(props.items.filter((it) => it.kind === f));
  const target = new Map(sub.placed.map((p) => [p.item.key, p]));
  // 新布局以自己的世界中心排布，对齐到全局世界中心
  const ox = (world.value.worldW - sub.worldW) / 2;
  const oy = (world.value.worldH - sub.worldH) / 2;
  let order = 0;
  placed.forEach((p, i) => {
    const t = target.get(p.item.key);
    if (!t || !pos[i]) return;
    gsap.to(pos[i], { x: t.x + ox, y: t.y + oy, duration: 1.05, ease: 'outExpo', delay: Math.min(order++, 8) * 0.03, overwrite: true });
  });
});

watch(() => props.items.length, () => gsap.delayedCall(0, () => { collectCards(); render(); }));

onMounted(() => {
  withIntro.value = !document.documentElement.classList.contains('curtain-seen');
  gsap.delayedCall((withIntro.value ? 1.15 : 0) + 2, () => { entering.value = false; });
  centerView();
  panX = initialPanX;
  panY = initialPanY;
  collectCards();
  render();

  tickerFn = tick;
  gsap.ticker.add(tickerFn);

  ro = new ResizeObserver(() => {
    const prevX = initialPanX;
    const prevY = initialPanY;
    centerView();
    panX += initialPanX - prevX;
    panY += initialPanY - prevY;
  });
  if (viewportRef.value) ro.observe(viewportRef.value);

  io = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; });
  if (viewportRef.value) io.observe(viewportRef.value);

  viewportRef.value?.addEventListener('wheel', onWheel, { passive: false });
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  if (tickerFn) gsap.ticker.remove(tickerFn);
  gsap.killTweensOf(pos);
  ro?.disconnect();
  io?.disconnect();
  viewportRef.value?.removeEventListener('wheel', onWheel);
  window.removeEventListener('keydown', onKeydown);
});

function pad(n?: number | null) {
  return String(n ?? 0).padStart(3, '0');
}

/** 小地图上的纸笺位置（以世界宽度为 100 的坐标） */
const miniDots = computed(() => {
  const { worldW } = world.value;
  return layout.value.map((p) => ({
    key: p.item.key,
    kind: p.item.kind,
    x: ((p.x + CARD_SIZE[p.item.kind][0] / 2) / worldW) * 100,
    y: ((p.y + CARD_SIZE[p.item.kind][1] / 2) / worldW) * 100,
  }));
});
const miniH = computed(() => (world.value.worldH / world.value.worldW) * 100);

defineExpose({ resetView });
</script>

<template>
  <div
    ref="viewportRef"
    class="canvas-viewport"
    :class="{ 'is-dragging': isDragging, 'is-entering': entering, 'with-intro': withIntro, [`filter-${filter}`]: true }"
    data-cursor="drag"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @click.capture="onClickCapture"
    @focusin="onFocusIn"
  >
    <InkPond class="canvas-pond" />

    <!-- 标题两层：墨层用差值混合「刻」在墨上；朱砂层保持本色。两层排版完全相同，只是各自隐藏另一半 -->
    <div ref="titleRef" class="canvas-title is-ink">
      <slot name="title" layer="ink" />
    </div>
    <div ref="titleAccentRef" class="canvas-title is-accent">
      <slot name="title" layer="accent" />
    </div>

    <div ref="surfaceRef" class="canvas-surface">
      <div
        v-for="p in layout"
        :key="p.item.key"
        class="canvas-card"
        :class="[`kind-${p.item.kind}`, { 'is-filtered': filter !== 'all' && filter !== p.item.kind }]"
        :style="{ '--d': `${p.delay.toFixed(3)}s` }"
      >
        <!-- 文章：一张带水墨封面的纸笺 -->
        <NuxtLink
          v-if="p.item.kind === 'post'"
          :to="p.item.href"
          class="card-inner card-post"
          data-cursor="read"
          draggable="false"
          :style="p.item.accent ? { '--card-accent': p.item.accent } : undefined"
        >
          <span class="card-cover">
            <InkCover :seed="p.item.slug || p.item.key" :no="p.item.number" :accent="p.item.accent" :width="288" :height="168" :numeral="false" />
          </span>
          <span class="card-meta">
            <span class="card-no">No. {{ pad(p.item.number) }}</span>
            <span>{{ p.item.meta }}</span>
          </span>
          <span class="card-title">{{ p.item.title }}</span>
          <span v-if="p.item.tags?.length" class="card-tags">
            <span v-for="t in p.item.tags.slice(0, 2)" :key="t">{{ t }}</span>
          </span>
        </NuxtLink>

        <!-- 项目：一张夜色的字模样张 -->
        <NuxtLink
          v-else-if="p.item.kind === 'project'"
          :to="p.item.href"
          class="card-inner card-project"
          data-cursor="open"
          draggable="false"
        >
          <span class="card-project-head">
            <span class="card-project-kicker">Project</span>
            <span v-if="p.item.stars != null" class="card-stars">★ {{ p.item.stars }}</span>
          </span>
          <span class="card-project-name">{{ p.item.title }}</span>
          <span class="card-excerpt">{{ p.item.excerpt }}</span>
          <span class="card-lang">
            <i :style="p.item.langColor ? { background: p.item.langColor } : undefined" />{{ p.item.lang || 'Code' }}
          </span>
        </NuxtLink>

        <!-- TIL：一段终端输出 -->
        <NuxtLink v-else :to="p.item.href" class="card-inner card-til" draggable="false">
          <span class="card-til-head">$ til <em>--tag {{ p.item.tags?.[0] || 'misc' }}</em></span>
          <span class="card-til-title">{{ p.item.title }}</span>
          <span class="card-excerpt">{{ p.item.excerpt }}</span>
          <span class="card-til-date">{{ p.item.meta }}</span>
        </NuxtLink>
      </div>
    </div>

    <!-- 套准坐标：读数 + 小地图 -->
    <div class="canvas-hud" aria-hidden="true">
      <UiCropMarks class="canvas-hud-mark" />
      <span ref="coordsRef" class="canvas-coords">X +0000  Y +0000</span>
    </div>
    <svg class="canvas-mini" :viewBox="`0 0 100 ${miniH}`" aria-hidden="true">
      <rect class="canvas-mini-frame" x="0" y="0" width="100" :height="miniH" />
      <circle v-for="d in miniDots" :key="d.key" :cx="d.x" :cy="d.y" r="0.9" :class="`is-${d.kind}`" />
      <rect ref="miniRef" class="canvas-mini-view" x="0" y="0" width="22" :height="13" />
    </svg>
  </div>
</template>

<style scoped>
.canvas-viewport {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  contain: strict;
  isolation: isolate;
}

.canvas-pond { z-index: 0; }

.canvas-viewport { background: var(--color-bg); }
.canvas-title {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  will-change: transform;
}
/* 墨层：差值混合。源色取近白：在纸上得到近黑的字，墨流过的地方字反白（夜间相反） */
.canvas-title.is-ink {
  mix-blend-mode: difference;
  color: oklch(98.5% 0.006 85);
  --mast-muted: oklch(62% 0.01 85);
}
.canvas-title.is-accent { z-index: 1; }

.canvas-surface {
  position: absolute;
  inset: 0;
  z-index: 2;
  transform-origin: 50% 50%;
  will-change: transform;
}

.canvas-card {
  position: absolute;
  top: 0;
  left: 0;
  will-change: transform;
}

/* 纸笺：浮在墨上，所以有一层极淡的投影；悬停时被指尖托起 */
.card-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--color-bg);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  box-shadow: var(--shadow-sm);
  transition:
    opacity 500ms var(--ease-out-quart),
    transform 700ms var(--ease-out-expo),
    border-color var(--dur-sm) ease;
  -webkit-user-drag: none;
}
.card-inner:hover {
  border-color: var(--color-line-strong);
  transform: translate3d(0, -6px, 0) rotate(-0.4deg);
}
.card-inner:active { transform: translate3d(0, -2px, 0) scale(0.985); transition-duration: 120ms; }

/* 入场：纸笺从墨里浮上来，离中心越远越晚 */
.canvas-viewport.is-entering .card-inner {
  animation: card-in 1200ms var(--ease-out-expo) backwards;
  animation-delay: calc(var(--d, 0s) + 0.1s);
}
.canvas-viewport.is-entering.with-intro .card-inner { animation-delay: calc(var(--d, 0s) + 1.15s); }
@keyframes card-in {
  from { opacity: 0; transform: translate3d(0, 36px, 0) scale(0.94); }
}
html.reduce-motion .canvas-viewport .card-inner { animation: none; }

/* 悬停时其他纸笺退后；拖拽中不触发 */
.canvas-viewport:not(.is-dragging) .canvas-surface:has(.card-inner:hover) .card-inner:not(:hover) { opacity: 0.4; }
.is-dragging .card-inner { transform: none !important; }

/* 被筛掉的纸笺沉入墨中 */
.is-filtered .card-inner {
  opacity: 0 !important;
  transform: scale(0.88) translate3d(0, 24px, 0) !important;
  pointer-events: none;
}

/* ---- 文章纸笺 ---- */
.card-post { width: 288px; }
.card-cover {
  position: relative;
  display: block;
  height: 168px;
  margin: -12px -12px 2px;
  overflow: hidden;
  border-bottom: 1px solid var(--color-line);
}
.card-cover :deep(.ink-cover) { transition: transform 1200ms var(--ease-out-expo); }
.card-post:hover .card-cover :deep(.ink-cover) { transform: scale(1.06); }
.card-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--color-ink-muted);
}
.card-no { color: var(--color-accent-text); letter-spacing: 0.1em; }
.card-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  line-height: 1.42;
  color: var(--color-ink);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-tags { display: flex; gap: 8px; font-size: 11px; color: var(--color-ink-muted); }
.card-tags span::before { content: "#"; color: var(--color-ink-faint); }

/* ---- 项目纸笺：夜色样张，任何时段都是深色 ---- */
.card-project {
  width: 260px;
  padding: 18px;
  background: var(--night-surface);
  border-color: color-mix(in oklab, var(--night-ink) 10%, transparent);
  color: var(--night-ink);
}
.card-project:hover { border-color: color-mix(in oklab, var(--night-ink) 22%, transparent); }
.card-project-kicker { font-family: var(--font-mono); font-size: var(--fs-nano); letter-spacing: 0.16em; text-transform: uppercase; color: color-mix(in oklab, var(--night-ink) 50%, transparent); }
.card-project-head { display: flex; justify-content: space-between; align-items: center; }
.card-stars { font-family: var(--font-mono); font-size: 11px; color: var(--night-accent); }
.card-project-name {
  margin-top: 14px;
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 600;
  line-height: 1.05;
  letter-spacing: -0.03em;
  font-variation-settings: "opsz" 72, "SOFT" 60;
}
.card-project .card-excerpt { color: color-mix(in oklab, var(--night-ink) 62%, transparent); }
.card-lang { display: inline-flex; align-items: center; gap: 7px; margin-top: 6px; font-family: var(--font-mono); font-size: 11px; color: color-mix(in oklab, var(--night-ink) 62%, transparent); }
.card-lang i { width: 8px; height: 8px; border-radius: 50%; background: var(--night-accent); }

.card-excerpt {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ---- TIL 纸笺 ---- */
.card-til {
  width: 236px;
  font-family: var(--font-mono);
  background: var(--color-surface);
}
.card-til-head { font-size: 11px; color: var(--color-accent-text); }
.card-til-head em { font-style: normal; color: var(--color-ink-muted); }
.card-til-title { font-family: var(--font-sans); font-size: 14px; font-weight: 600; line-height: 1.45; color: var(--color-ink); }
.card-til .card-excerpt { font-family: var(--font-mono); font-size: 11.5px; }
.card-til-date { font-size: 10.5px; color: var(--color-ink-faint); }

/* ---- 套准坐标 ---- */
.canvas-hud {
  position: absolute;
  left: var(--page-padding);
  bottom: 28px;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 30px;
  padding: 0 12px 0 10px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  color: var(--color-ink-muted);
  font-variant-numeric: tabular-nums;
  white-space: pre;
  background: var(--color-paper-glass);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  pointer-events: none;
}
.canvas-hud-mark { width: 12px; height: 12px; color: var(--color-accent); }
.canvas-mini {
  position: absolute;
  right: var(--page-padding);
  bottom: 28px;
  z-index: 4;
  width: 112px;
  height: auto;
  overflow: visible;
  pointer-events: none;
}
.canvas-mini-frame { fill: var(--color-paper-glass); stroke: var(--color-line-strong); stroke-width: 0.6; }
.canvas-mini circle { fill: var(--color-ink-faint); }
.canvas-mini circle.is-post { fill: var(--color-ink); }
.canvas-mini circle.is-project { fill: var(--color-accent); }
.canvas-mini-view { fill: none; stroke: var(--color-accent); stroke-width: 0.8; }
@media (max-width: 760px) {
  .canvas-hud, .canvas-mini { display: none; }
}
</style>
