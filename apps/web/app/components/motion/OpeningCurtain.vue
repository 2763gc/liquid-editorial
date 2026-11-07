<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import gsap from 'gsap';
import { DUR, sec } from '~/composables/motion/tokens';

/**
 * M1 开场序幕：印刷机开机，压出本期刊名
 * - 站名逐字压印（wght 200→800、scale 1.015→1），计数 000→100，随后朱砂衬纸带着墨版上揭。总时长 ≤ 1.6 秒
 * - 点击或按任意键跳过（直接快进到上揭）
 * - 服务端直接渲染遮罩，避免「先看到页面再盖上遮罩」的闪烁；是否已播放由 <head> 内联脚本写入 html.curtain-seen
 * - 只在 html.js 存在时显示：禁用 JS 时遮罩永远不会出现（B26）
 */
const shown = ref(true);
const rootRef = ref<HTMLElement | null>(null);
const counterRef = ref<HTMLElement | null>(null);
const WORD = 'LUNTRIX'.split('');
let tl: gsap.core.Timeline | null = null;

function skip() {
  if (!tl || tl.progress() > 0.62) return;
  // 快进到上揭开始的位置，保留最后的揭幕，不硬切
  tl.seek('lift');
}

onMounted(async () => {
  const root = document.documentElement;
  if (root.classList.contains('curtain-seen')) {
    shown.value = false;
    return;
  }
  await nextTick();
  const el = rootRef.value;
  if (!el) return;
  root.style.overflow = 'hidden';

  const letters = el.querySelectorAll<HTMLElement>('.curtain-letter');
  const counter = { v: 0 };
  const panel = el.querySelector('.curtain-panel');
  const trail = el.querySelector('.curtain-trail');
  const bar = el.querySelector('.curtain-bar i');
  const inner = el.querySelector('.curtain-inner');

  tl = gsap.timeline({
    defaults: { ease: 'outExpo' },
    onComplete: () => {
      try { sessionStorage.setItem('seen_curtain', '1'); } catch {}
      root.classList.add('curtain-seen');
      root.style.overflow = '';
      shown.value = false;
      window.removeEventListener('keydown', skip);
    },
  });

  // 压印：每个字母由细到粗、由略大落定，错峰 60ms
  tl.fromTo(letters, { '--wght': 200, scale: 1.015, opacity: 0 }, { '--wght': 800, scale: 1, opacity: 1, duration: 0.42, ease: 'impress', stagger: 0.06 }, 0.05)
    .to(counter, {
      v: 100,
      duration: 0.95,
      ease: 'inOutQuart',
      onUpdate: () => {
        if (counterRef.value) counterRef.value.textContent = String(Math.round(counter.v)).padStart(3, '0');
      },
    }, 0)
    .fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.95, ease: 'inOutQuart' }, 0)
    .addLabel('lift', 1.0)
    // 揭版：墨版先揭起，朱砂衬纸紧随其后
    .to(inner, { yPercent: -14, opacity: 0, duration: 0.36, ease: 'inQuart' }, 'lift')
    .to(panel, { yPercent: -100, duration: sec(DUR.feed + 80), ease: 'inOutQuart' }, 'lift+=0.02')
    .to(trail, { yPercent: -100, duration: sec(DUR.feed + 60), ease: 'inOutQuart' }, 'lift+=0.1');

  window.addEventListener('keydown', skip, { once: false });
});

onBeforeUnmount(() => {
  tl?.kill();
  window.removeEventListener('keydown', skip);
  document.documentElement.style.overflow = '';
});
</script>

<template>
  <div v-if="shown" ref="rootRef" class="opening-curtain" aria-hidden="true" @click="skip">
    <div class="curtain-trail" />
    <div class="curtain-panel">
      <div class="curtain-inner">
        <div class="curtain-top">
          <span>VOL. 2026</span>
          <UiCropMarks class="curtain-crop" />
          <span>LIQUID EDITORIAL</span>
        </div>
        <div class="curtain-word">
          <span v-for="(ch, i) in WORD" :key="i" class="curtain-letter">{{ ch }}</span>
        </div>
        <div class="curtain-bottom">
          <span>一份关于软件、系统与审美的刊物 · 点击跳过</span>
          <span class="curtain-counter"><span ref="counterRef">000</span></span>
        </div>
        <div class="curtain-bar"><i /></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.opening-curtain {
  position: fixed;
  inset: 0;
  z-index: var(--z-curtain);
  display: none;
}
/* 只在脚本可用、且本会话未播放过时出现 */
:global(html.js:not(.curtain-seen) .opening-curtain) { display: block; }

.curtain-panel,
.curtain-trail {
  position: absolute;
  inset: 0;
  will-change: transform;
}
.curtain-trail { background: var(--color-accent); }
/* 墨版：不随时段变化的夜色 */
.curtain-panel {
  background: var(--night-bg);
  color: var(--night-ink);
  overflow: hidden;
}

.curtain-inner {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: clamp(20px, 4vw, 56px);
}
.curtain-bar {
  position: absolute;
  left: clamp(20px, 4vw, 56px);
  right: clamp(20px, 4vw, 56px);
  bottom: clamp(12px, 2vw, 28px);
  height: 1px;
  background: color-mix(in oklab, var(--night-ink) 12%, transparent);
}
.curtain-bar i {
  position: absolute;
  inset: 0;
  background: var(--color-accent);
  transform: scaleX(0);
  transform-origin: 0 50%;
}
.curtain-top,
.curtain-bottom {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: color-mix(in oklab, var(--night-ink) 50%, transparent);
}
.curtain-crop { width: 22px; height: 22px; color: var(--color-accent); }
.curtain-word {
  display: flex;
  justify-content: center;
  font-family: var(--font-display);
  font-size: clamp(64px, 17vw, 260px);
  line-height: 0.9;
  letter-spacing: -0.04em;
}
.curtain-letter {
  --wght: 200;
  display: inline-block;
  opacity: 0;
  font-variation-settings: "wght" var(--wght), "opsz" 144, "SOFT" 50;
  font-weight: 800;
}
.curtain-counter {
  font-size: clamp(28px, 4vw, 56px);
  font-weight: 500;
  letter-spacing: -0.02em;
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 560px) {
  .curtain-bottom > span:first-child { max-width: 14em; line-height: 1.6; }
}
</style>
