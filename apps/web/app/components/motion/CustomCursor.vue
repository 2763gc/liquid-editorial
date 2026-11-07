<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, nextTick } from 'vue';
import gsap from 'gsap';
import { onReducedChange } from '~/composables/useMotion';

/**
 * M6 上下文光标 2.0：光标是一滴墨（任务书 §4.7，只在桌面端）
 * - 圆点 + 跟随圆环；位置只写 transform（gsap.quickTo），不经过 Vue 响应式
 * - 语境：卡片「阅读」、画布「拖拽」、图片「放大」、代码块「复制」、外链「↗ 外链」
 * - 拖拽画布时圆环沿速度方向拉长成椭圆（最大 1.6 倍），像墨滴被甩出去
 * - 选中文字时隐藏圆环；触屏 / 减弱动效时不渲染
 */
const enabled = ref(false);
const dotRef = ref<HTMLElement | null>(null);
const ringRef = ref<HTMLElement | null>(null);
const shapeRef = ref<HTMLElement | null>(null);
const labelRef = ref<HTMLElement | null>(null);

const LABELS: Record<string, string> = { drag: '拖拽', read: '阅读', zoom: '放大', open: '打开', copy: '复制', external: '↗ 外链' };

let cleanup: (() => void) | null = null;
let offReduced: (() => void) | null = null;

async function start() {
  const fine = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
  if (!fine || document.documentElement.classList.contains('reduce-motion') || enabled.value) return;
  enabled.value = true;
  await nextTick();

  const dot = dotRef.value;
  const ring = ringRef.value;
  const shape = shapeRef.value;
  const label = labelRef.value;
  if (!dot || !ring || !shape || !label) return;
  document.documentElement.classList.add('has-custom-cursor');

  gsap.set([dot, ring], { xPercent: -50, yPercent: -50, x: -100, y: -100 });
  // 纸签贴在光标右下方 14px 处
  gsap.set(label, { xPercent: 0, yPercent: 0, x: -100, y: -100, transformOrigin: '0 0' });
  const dotX = gsap.quickTo(dot, 'x', { duration: 0.08, ease: 'outQuart' });
  const dotY = gsap.quickTo(dot, 'y', { duration: 0.08, ease: 'outQuart' });
  const ringX = gsap.quickTo(ring, 'x', { duration: 0.42, ease: 'outExpo' });
  const ringY = gsap.quickTo(ring, 'y', { duration: 0.42, ease: 'outExpo' });
  const labelX = gsap.quickTo(label, 'x', { duration: 0.42, ease: 'outExpo' });
  const labelY = gsap.quickTo(label, 'y', { duration: 0.42, ease: 'outExpo' });
  const stretch = gsap.quickTo(shape, 'scaleX', { duration: 0.3, ease: 'outQuart' });
  const squash = gsap.quickTo(shape, 'scaleY', { duration: 0.3, ease: 'outQuart' });

  let state = '';
  let visible = false;
  let pressed = false;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let lastT = 0;
  let selecting = false;

  function setState(next: string) {
    if (next === state) return;
    state = next;
    const text = LABELS[next] || '';
    label.textContent = text;
    // 有语境时圆环收成一枚小朱砂圈，文字以一张小纸签贴在光标右下，不再用大红圆盘盖住内容
    const scale = text ? 0.62 : next === 'link' ? 1.45 : next === 'text' ? 0.5 : 1;
    gsap.to(ring, { scale: pressed ? scale * 0.85 : scale, duration: 0.4, ease: 'outExpo', overwrite: 'auto' });
    gsap.to(dot, { scale: next === 'link' ? 0 : 1, duration: 0.25, ease: 'outQuart', overwrite: 'auto' });
    ring.classList.toggle('has-label', !!text);
    gsap.to(label, { opacity: text ? 1 : 0, scale: text ? 1 : 0.85, duration: text ? 0.36 : 0.18, ease: text ? 'outExpo' : 'inQuart', overwrite: 'auto' });
  }

  function onMove(e: PointerEvent) {
    if (e.pointerType !== 'mouse') return;
    if (!visible) {
      visible = true;
      gsap.set([dot, ring], { x: e.clientX, y: e.clientY });
      gsap.set(label, { x: e.clientX + 14, y: e.clientY + 14 });
      gsap.to([dot, ring], { opacity: 1, duration: 0.2 });
    }
    dotX(e.clientX);
    dotY(e.clientY);
    ringX(e.clientX);
    ringY(e.clientY);
    labelX(e.clientX + 14);
    labelY(e.clientY + 14);

    // 拖拽中：沿速度方向拉长
    const now = e.timeStamp;
    if (dragging && lastT) {
      const dt = Math.max(1, now - lastT);
      const vx = (e.clientX - lastX) / dt;
      const vy = (e.clientY - lastY) / dt;
      const speed = Math.hypot(vx, vy);
      if (speed > 0.05) gsap.set(shape, { rotation: (Math.atan2(vy, vx) * 180) / Math.PI });
      const s = Math.min(1.6, 1 + speed * 0.35);
      stretch(s);
      squash(1 / Math.sqrt(s));
    }
    lastX = e.clientX;
    lastY = e.clientY;
    lastT = now;

    const target = e.target as Element | null;
    const ctx = target?.closest?.('[data-cursor], a, button, [role="button"], input, textarea, select, label, [contenteditable="true"], .code-block, .terminal-block');
    if (!ctx) return setState('');
    const mode = ctx.getAttribute('data-cursor');
    if (mode) return setState(mode);
    const tag = ctx.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || ctx.getAttribute('contenteditable') === 'true') return setState('text');
    if (ctx.matches('.code-block, .terminal-block')) return setState('copy');
    if (ctx instanceof HTMLAnchorElement && ctx.target === '_blank') return setState('external');
    setState('link');
  }

  function onLeave() {
    visible = false;
    gsap.to([dot, ring], { opacity: 0, duration: 0.2 });
  }
  function onDown(e: PointerEvent) {
    pressed = true;
    dragging = !!(e.target as Element | null)?.closest?.('[data-cursor="drag"]');
    gsap.to(ring, { scale: '*=0.85', duration: 0.15, overwrite: 'auto' });
  }
  function onUp() {
    pressed = false;
    if (dragging) {
      dragging = false;
      stretch(1);
      squash(1);
    }
    const s = state;
    state = '__';
    setState(s);
  }
  function onSelection() {
    const sel = document.getSelection();
    const has = !!sel && !sel.isCollapsed && sel.toString().trim().length > 0;
    if (has === selecting) return;
    selecting = has;
    gsap.to(ring, { opacity: has ? 0 : 1, duration: 0.2, overwrite: 'auto' });
  }

  window.addEventListener('pointermove', onMove, { passive: true });
  window.addEventListener('pointerdown', onDown, { passive: true });
  window.addEventListener('pointerup', onUp, { passive: true });
  document.addEventListener('selectionchange', onSelection);
  document.documentElement.addEventListener('pointerleave', onLeave);

  cleanup = () => {
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerdown', onDown);
    window.removeEventListener('pointerup', onUp);
    document.removeEventListener('selectionchange', onSelection);
    document.documentElement.removeEventListener('pointerleave', onLeave);
    document.documentElement.classList.remove('has-custom-cursor');
    gsap.killTweensOf([dot, ring, label, shape]);
    enabled.value = false;
  };
}

onMounted(() => {
  start();
  offReduced = onReducedChange((reduced) => {
    if (reduced) {
      cleanup?.();
      cleanup = null;
    } else start();
  });
});

onBeforeUnmount(() => {
  cleanup?.();
  offReduced?.();
});
</script>

<template>
  <div v-if="enabled" class="custom-cursor-layer" aria-hidden="true">
    <div ref="ringRef" class="cursor-ring"><i ref="shapeRef" class="cursor-ring-shape" /></div>
    <span ref="labelRef" class="cursor-label" />
    <div ref="dotRef" class="cursor-dot" />
  </div>
</template>

<style scoped>
.custom-cursor-layer {
  position: fixed;
  inset: 0;
  z-index: var(--z-cursor);
  pointer-events: none;
}
.cursor-dot,
.cursor-ring {
  position: fixed;
  top: 0;
  left: 0;
  opacity: 0;
  will-change: transform;
  pointer-events: none;
}
.cursor-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
}
.cursor-ring {
  width: 34px;
  height: 34px;
}
.cursor-ring-shape {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid color-mix(in oklab, var(--color-ink) 35%, transparent);
  transition: background-color 250ms ease, border-color 250ms ease;
}
.cursor-ring.has-label .cursor-ring-shape {
  border-color: var(--color-accent);
  border-width: 1.5px;
}
/* 纸签：小号等宽字，墨底纸字，发丝描边 */
.cursor-label {
  position: fixed;
  top: 0;
  left: 0;
  opacity: 0;
  pointer-events: none;
  padding: 4px 7px 4px 8px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: 0.12em;
  color: var(--color-bg);
  background: var(--color-ink);
  border-radius: 2px;
  box-shadow: var(--shadow-sm);
  white-space: nowrap;
}
</style>
