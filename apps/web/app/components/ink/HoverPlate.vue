<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';
import { frameLerp } from '~/composables/motion/tokens';

/**
 * 悬停浮图：光标停在带 data-plate 的条目上时，这篇文章的水墨封面带着惯性跟随光标浮现，
 * 随移动速度轻微倾斜；出现时从边缘洇开（噪声遮罩由小到大），离开时快速收起。
 * 只在桌面细指针、非减弱动效时启用。条目上需要 data-plate（种子）、可选 data-plate-no / data-plate-accent。
 */
const props = defineProps<{ scope: HTMLElement | null }>();

const plateRef = ref<HTMLElement | null>(null);
const seed = ref('');
const no = ref<number | null>(null);
const accent = ref<string | null>(null);
const on = ref(false);
let enabled = false;
let x = 0;
let y = 0;
let tx = 0;
let ty = 0;
let tilt = 0;
let showTimer = 0;
let current: HTMLElement | null = null;

function tick(_t: number, dt: number) {
  const el = plateRef.value;
  if (!el) return;
  const k = frameLerp(0.14, dt);
  const px = x;
  x += (tx - x) * k;
  y += (ty - y) * k;
  tilt += (Math.max(-10, Math.min(10, (x - px) * 0.6)) - tilt) * frameLerp(0.1, dt);
  el.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) rotate(${tilt.toFixed(2)}deg)`;
}

function onMove(e: PointerEvent) {
  if (e.pointerType !== 'mouse') return;
  tx = e.clientX + 28;
  ty = e.clientY - 120;
  const row = (e.target as Element | null)?.closest?.<HTMLElement>('[data-plate]') || null;
  if (row === current) return;
  current = row;
  window.clearTimeout(showTimer);
  if (!row) {
    on.value = false;
    return;
  }
  // 悬停意图：60ms 后才浮现，快速划过时不闪
  showTimer = window.setTimeout(() => {
    seed.value = row.dataset.plate || '';
    no.value = row.dataset.plateNo ? Number(row.dataset.plateNo) : null;
    accent.value = row.dataset.plateAccent || null;
    if (!on.value) { x = tx; y = ty; }
    on.value = true;
  }, 60);
}
function onLeave() {
  current = null;
  window.clearTimeout(showTimer);
  on.value = false;
}

onMounted(() => {
  const root = document.documentElement;
  enabled = matchMedia('(hover: hover) and (pointer: fine)').matches && !root.classList.contains('reduce-motion');
  if (!enabled || !props.scope) return;
  props.scope.addEventListener('pointermove', onMove, { passive: true });
  props.scope.addEventListener('pointerleave', onLeave);
  gsap.ticker.add(tick);
});
onBeforeUnmount(() => {
  window.clearTimeout(showTimer);
  props.scope?.removeEventListener('pointermove', onMove);
  props.scope?.removeEventListener('pointerleave', onLeave);
  gsap.ticker.remove(tick);
});
</script>

<template>
  <div ref="plateRef" class="hover-plate" :class="{ 'is-on': on }" aria-hidden="true">
    <div class="hover-plate-inner">
      <InkCover v-if="seed" :key="seed" :seed="seed" :no="no" :accent="accent" :width="320" :height="220" />
    </div>
  </div>
</template>

<style scoped>
.hover-plate {
  position: fixed;
  left: 0;
  top: 0;
  z-index: calc(var(--z-header) - 1);
  width: 300px;
  height: 206px;
  pointer-events: none;
  will-change: transform;
}
.hover-plate-inner {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border: 1px solid var(--color-line-strong);
  box-shadow: var(--shadow-lg);
  -webkit-mask-image: var(--ink-blot);
  mask-image: var(--ink-blot);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: 50% 50%;
  mask-position: 50% 50%;
  -webkit-mask-size: 0% 0%;
  mask-size: 0% 0%;
  opacity: 0;
  transform: scale(0.94);
  transition: -webkit-mask-size 300ms var(--ease-in-quart), mask-size 300ms var(--ease-in-quart), opacity 300ms var(--ease-in-quart), transform 300ms var(--ease-in-quart);
}
/* 洇开：墨迹遮罩从中心放大到盖住整张图，最后摘掉遮罩露出直边 */
.hover-plate.is-on .hover-plate-inner {
  -webkit-mask-size: 320% 320%;
  mask-size: 320% 320%;
  opacity: 1;
  transform: none;
  transition: -webkit-mask-size 500ms var(--ease-out-quart), mask-size 500ms var(--ease-out-quart), opacity 240ms var(--ease-out-quart), transform 500ms var(--ease-out-expo);
}
</style>
