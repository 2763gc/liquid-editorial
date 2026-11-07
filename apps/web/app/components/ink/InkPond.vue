<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';
import { InkFluid, cssColorToRgb } from '~/utils/inkFluid';
import { onReducedChange } from '~/composables/useMotion';

/**
 * 墨池（首页主角）：一方可以用指尖搅动的墨。
 * - 光标与拖拽在墨池里留下涡流；在空白处点一下，落下一滴墨；点标题，落下一点朱砂
 * - 开场时几笔墨从标题两侧晕开，之后静静沉淀；长时间无操作，偶尔有一滴墨从上方落下
 * - 高档：128 网格 / 512 墨；中档与触屏：减半；低档与减弱动效：只模拟一次，定格成一幅水墨
 * - 不在视口内、页面隐藏时停止模拟
 */
const props = withDefaults(defineProps<{ seed?: number; interactive?: boolean; tone?: 'auto' | 'light' | 'dark' }>(), { seed: 7, interactive: true, tone: 'auto' });
const emit = defineEmits<{ (e: 'ready', ok: boolean): void }>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const failed = ref(false);
let fluid: InkFluid | null = null;
let running = false;
let visible = true;
let io: IntersectionObserver | null = null;
let ro: ResizeObserver | null = null;
let lastX = -1;
let lastY = -1;
let lastMove = 0;
let idle = 0;
let still = false;
let offReduced: (() => void) | null = null;
let themeObserver: MutationObserver | null = null;

function rng(seed: number) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function colors() {
  if (!fluid) return;
  const dark = props.tone === 'dark' || (props.tone === 'auto' && document.documentElement.getAttribute('data-theme') === 'dark');
  // 昼：浓墨；夜：银墨（月光落在墨池上）
  fluid.setColors(cssColorToRgb(dark ? 'oklch(84% 0.014 85)' : 'oklch(20% 0.012 65)'), cssColorToRgb('var(--color-accent)'));
  fluid.strength = dark ? 0.62 : 0.9;
}

function sizeCanvas() {
  const c = canvasRef.value;
  if (!c) return false;
  const tier = document.documentElement.getAttribute('data-tier');
  const dpr = tier === 'high' ? Math.min(window.devicePixelRatio || 1, 1.5) : 0.75;
  const w = Math.max(1, Math.round(c.clientWidth * dpr));
  const h = Math.max(1, Math.round(c.clientHeight * dpr));
  if (c.width === w && c.height === h) return false;
  c.width = w;
  c.height = h;
  return true;
}

/** 开场的几笔：从标题两侧晕开、带一点回旋 */
function opening() {
  if (!fluid) return;
  const r = rng(props.seed);
  // 留白为先：两三笔浓墨落在标题两侧的远处，其余是极淡的晕
  const strokes = 6;
  for (let i = 0; i < strokes; i++) {
    const side = i % 2 ? 1 : -1;
    const x = 0.5 + side * (0.26 + r() * 0.2);
    const y = 0.22 + r() * 0.56;
    const angle = r() * Math.PI * 2;
    const f = 260 + r() * 360;
    const heavy = i < 2;
    fluid.splat(x, y, Math.cos(angle) * f, Math.sin(angle) * f, heavy ? 0.42 + r() * 0.2 : 0.1 + r() * 0.12, 0, heavy ? 0.0011 + r() * 0.0008 : 0.0016 + r() * 0.0016);
  }
  // 一点朱砂
  fluid.splat(0.5 + (r() - 0.5) * 0.6, 0.74 + r() * 0.1, (r() - 0.5) * 240, -180, 0, 0.42, 0.0006);
}

function tick(_t: number, dt: number) {
  if (!fluid || !visible || still) return;
  idle += dt;
  // 长时间无人搅动：偶尔有一滴墨从上方落下，像檐下的水
  if (idle > 9000) {
    idle = 0;
    const r = Math.random;
    fluid.splat(0.1 + r() * 0.8, 0.05 + r() * 0.15, (r() - 0.5) * 100, 360 + r() * 220, 0.22 + r() * 0.18, 0, 0.0009);
  }
  fluid.step(dt);
  fluid.render();
}

function onMove(e: PointerEvent) {
  const c = canvasRef.value;
  if (!fluid || !c || still) return;
  const r = c.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width;
  const y = (e.clientY - r.top) / r.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) {
    lastX = -1;
    return;
  }
  const now = e.timeStamp;
  if (lastX >= 0 && now - lastMove < 120) {
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    const speed = Math.hypot(dx, dy);
    if (speed > 0.5) {
      // 像素位移 → 网格速度（texel/s）
      const k = (128 / r.height) * 90;
      // 指尖划过只带起很淡的一缕墨，主要是把已有的墨搅开
      const ink = Math.min(0.09, speed * 0.0022);
      fluid.splat(x, y, dx * k, dy * k, ink, 0, 0.0007);
    }
  }
  lastX = e.clientX;
  lastY = e.clientY;
  lastMove = now;
  idle = 0;
}

function onDown(e: PointerEvent) {
  const c = canvasRef.value;
  if (!fluid || !c || still) return;
  const target = e.target as Element | null;
  // 在卡片上按下是要打开或拖拽，不落墨
  if (target?.closest?.('.canvas-card, button, a:not(.pond-title-link)')) return;
  const r = c.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width;
  const y = (e.clientY - r.top) / r.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return;
  const onTitle = !!target?.closest?.('[data-pond-title]');
  fluid.splat(x, y, 0, 0, onTitle ? 0 : 0.6, onTitle ? 0.75 : 0, onTitle ? 0.0008 : 0.0014);
  idle = 0;
}

function start() {
  if (running) return;
  running = true;
  gsap.ticker.add(tick);
}
function stop() {
  if (!running) return;
  running = false;
  gsap.ticker.remove(tick);
}

/** 只模拟若干步并定格：减弱动效、低档设备 */
function freeze() {
  if (!fluid) return;
  stop();
  still = true;
  for (let i = 0; i < 110; i++) fluid.step(16.7);
  fluid.render();
}

function init() {
  const c = canvasRef.value;
  if (!c) return;
  const root = document.documentElement;
  const tier = root.getAttribute('data-tier');
  const coarse = root.getAttribute('data-pointer') === 'coarse';
  sizeCanvas();
  const small = tier !== 'high' || coarse;
  fluid = new InkFluid(c, { simRes: small ? 72 : 128, dyeRes: small ? 320 : 512, iterations: small ? 12 : 20 });
  if (!fluid.ok) {
    failed.value = true;
    fluid = null;
    emit('ready', false);
    return;
  }
  colors();
  opening();
  emit('ready', true);
  if (root.classList.contains('reduce-motion') || tier === 'low') {
    freeze();
    return;
  }
  start();
  if (props.interactive) {
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
  }
}

onMounted(() => {
  init();
  io = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
  if (canvasRef.value) io.observe(canvasRef.value);
  ro = new ResizeObserver(() => {
    if (!fluid || !sizeCanvas()) return;
    fluid.resize();
    opening();
    if (still) freeze();
  });
  if (canvasRef.value) ro.observe(canvasRef.value);
  themeObserver = new MutationObserver(() => {
    colors();
    if (still) fluid?.render();
  });
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-period'] });
  offReduced = onReducedChange((reduced) => {
    if (reduced) freeze();
    else if (fluid) {
      still = false;
      start();
    }
  });
});

onBeforeUnmount(() => {
  stop();
  window.removeEventListener('pointermove', onMove);
  window.removeEventListener('pointerdown', onDown);
  io?.disconnect();
  ro?.disconnect();
  themeObserver?.disconnect();
  offReduced?.();
  fluid?.dispose();
  fluid = null;
});
</script>

<template>
  <div class="ink-pond" :class="{ 'is-failed': failed }" aria-hidden="true">
    <canvas ref="canvasRef" class="ink-pond-canvas" />
  </div>
</template>

<style scoped>
.ink-pond {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.ink-pond-canvas { width: 100%; height: 100%; display: block; }
/* 没有 WebGL2：一幅静态的水墨晕染代替 */
.ink-pond.is-failed {
  background:
    radial-gradient(38% 30% at 24% 42%, color-mix(in oklab, var(--color-ink) 22%, transparent), transparent 70%),
    radial-gradient(30% 26% at 78% 60%, color-mix(in oklab, var(--color-ink) 16%, transparent), transparent 70%),
    radial-gradient(6% 5% at 62% 74%, color-mix(in oklab, var(--color-accent) 50%, transparent), transparent 70%);
  -webkit-mask-image: var(--ink-blot);
  mask-image: var(--ink-blot);
  -webkit-mask-size: 140% 160%;
  mask-size: 140% 160%;
  -webkit-mask-position: 50% 45%;
  mask-position: 50% 45%;
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
}
.ink-pond.is-failed canvas { display: none; }
</style>
