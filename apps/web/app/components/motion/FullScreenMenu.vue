<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import gsap from 'gsap';
import { lockScroll, unlockScroll } from '~/composables/useLenis';
import { useMagnetic } from '~/composables/motion/useMagnetic';
import { staggerFor } from '~/composables/motion/tokens';

/**
 * M11 全屏菜单 · 本期目录页
 * - 一滴墨从菜单按钮处洇开，铺成一页纸色的目录（墨迹遮罩由小到大，边缘不规则）
 * - 条目是超大字号的栏目名 + 引导点 + 页码（§ 01…），编号与各栏目刊头一致
 * - 悬停条目，这个栏目的水墨封面带着惯性跟随光标浮现（<InkHoverPlate>）
 * - 可中断：开合用同一条时间线，动画中途再按就从当前进度反向，不排队、不忽略点击
 */
const route = useRoute();
const isOpen = ref(false);
const overlayRef = ref<HTMLElement | null>(null);
const listRef = ref<HTMLElement | null>(null);
const triggerRef = ref<HTMLElement | null>(null);
let tl: gsap.core.Timeline | null = null;
useMagnetic(triggerRef, 6);

const menuItems = [
  { no: '01', title: '墨池', en: 'Index', path: '/', desc: '可以搅动的首页画布' },
  { no: '02', title: '特稿', en: 'Features', path: '/posts', desc: '深度长文与系统拆解' },
  { no: '03', title: '专栏', en: 'Series', path: '/series', desc: '体系化的技术长卷' },
  { no: '04', title: '项目', en: 'Projects', path: '/projects', desc: '开源作品与字模样张' },
  { no: '05', title: '今日所学', en: 'TIL', path: '/til', desc: '终端里的知识切片' },
  { no: '06', title: '时间之河', en: 'Archive', path: '/archive', desc: '按年月流过的合订本' },
  { no: '07', title: '关于', en: 'About', path: '/about', desc: '编辑部与工程履历' },
  { no: '08', title: '工具', en: 'Uses', path: '/uses', desc: '硬件、终端与开发套件' },
  { no: '09', title: '友链', en: 'Links', path: '/links', desc: '数字邻居与同行者' },
];

function origin() {
  const r = triggerRef.value?.getBoundingClientRect();
  if (!r) return { x: window.innerWidth - 40, y: 32 };
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}

function build(el: HTMLElement) {
  const { x, y } = origin();
  const reduce = document.documentElement.classList.contains('reduce-motion');
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
  // 墨迹遮罩里的圆半径是画幅的 35%，盖住最远的角需要放大到 r / 0.35
  const size = (r / 0.35) * 1.12;
  const lines = el.querySelectorAll('.menu-line-inner');
  const fades = el.querySelectorAll('.menu-fade');
  const t = gsap.timeline({
    paused: true,
    onReverseComplete: () => {
      isOpen.value = false;
      unlockScroll();
      triggerRef.value?.focus({ preventScroll: true });
    },
  });
  if (reduce) {
    t.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: 'none' });
    return t;
  }
  t.fromTo(el,
    { '--menu-size': '0px', '--menu-x': `${x}px`, '--menu-y': `${y}px` },
    { '--menu-size': `${size}px`, '--menu-x': `${x - size / 2}px`, '--menu-y': `${y - size / 2}px`, duration: 0.82, ease: 'inOutQuart' }, 0)
    .fromTo(lines, { yPercent: 108 }, { yPercent: 0, duration: 0.9, stagger: staggerFor(lines.length), ease: 'outExpo' }, 0.34)
    .fromTo(fades, { opacity: 0 }, { opacity: 1, duration: 0.5, stagger: staggerFor(fades.length, 30), ease: 'outQuart' }, 0.5)
    .fromTo(el.querySelectorAll('.leader'), { scaleX: 0 }, { scaleX: 1, duration: 0.9, stagger: 0.03, ease: 'outExpo' }, 0.5);
  return t;
}

async function open() {
  if (isOpen.value && tl && !tl.reversed()) return;
  if (isOpen.value && tl) {
    // 正在合上：就地改道，重新展开
    tl.timeScale(1).play();
    return;
  }
  isOpen.value = true;
  lockScroll();
  await nextTick();
  const el = overlayRef.value;
  if (!el) return;
  tl?.kill();
  tl = build(el);
  tl.play();
  el.querySelector<HTMLElement>('.menu-link')?.focus({ preventScroll: true });
}

function close() {
  if (!isOpen.value || !tl) return;
  // 离开比进入更快
  tl.timeScale(1.7).reverse();
}

function toggle() {
  if (isOpen.value && tl && !tl.reversed()) close();
  else open();
}

function isTyping(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
}

function onKeydown(e: KeyboardEvent) {
  if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e)) return;
  if (e.key === 'm' || e.key === 'M') {
    e.preventDefault();
    toggle();
  } else if (e.key === 'Escape' && isOpen.value) {
    close();
  }
}

/** 点了菜单里的链接：新页面直接换上，菜单随之消失，不再播放合上的动画 */
watch(() => route.fullPath, () => {
  if (!isOpen.value) return;
  tl?.kill();
  tl = null;
  isOpen.value = false;
  unlockScroll();
});

onMounted(() => window.addEventListener('keydown', onKeydown));
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  tl?.kill();
  if (isOpen.value) unlockScroll();
});

defineExpose({ open, close, toggle });
</script>

<template>
  <button
    ref="triggerRef"
    type="button"
    class="menu-trigger"
    :class="{ 'is-open': isOpen }"
    :aria-expanded="isOpen"
    aria-controls="site-menu"
    aria-label="打开目录"
    @click="toggle"
  >
    <span class="menu-trigger-label">目录</span>
    <span class="menu-trigger-icon" aria-hidden="true"><i /><i /></span>
  </button>

  <Teleport to="body">
    <div
      v-if="isOpen"
      id="site-menu"
      ref="overlayRef"
      class="menu-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="本期目录"
      data-lenis-prevent
    >
      <div class="menu-head page-shell">
        <p class="menu-masthead menu-fade">
          <span class="menu-vol">Liquid Editorial · Vol. 2026</span>
          <span class="menu-heading font-display">Contents <em>本期目录</em></span>
        </p>
        <button type="button" class="menu-close menu-fade" aria-label="合上目录" @click="close">
          <kbd>Esc</kbd> 合上 <span class="menu-close-x" aria-hidden="true"><i /><i /></span>
        </button>
      </div>

      <nav ref="listRef" class="menu-list page-shell" aria-label="栏目">
        <InkHoverPlate :scope="listRef" />
        <NuxtLink
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="menu-link"
          :class="{ 'is-current': item.path === '/' ? route.path === '/' : route.path.startsWith(item.path) }"
          :data-plate="item.en"
        >
          <span class="menu-index menu-fade">§ {{ item.no }}</span>
          <span class="menu-line-mask"><span class="menu-line-inner">{{ item.title }}</span></span>
          <span class="leader" aria-hidden="true" />
          <span class="menu-desc menu-fade">{{ item.desc }}</span>
          <span class="menu-page menu-fade">{{ item.en }}</span>
        </NuxtLink>
      </nav>

      <div class="menu-foot page-shell menu-fade">
        <span>按 <kbd>M</kbd> 打开或合上目录 · <kbd>⌘</kbd><kbd>K</kbd> 检字</span>
        <a href="/rss.xml" target="_blank" rel="noopener" class="link-draw">RSS 订阅</a>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.menu-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 6px 0 14px;
  font-family: var(--font-sans);
  font-size: var(--fs-micro);
  font-weight: 500;
  letter-spacing: 0.04em;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-pill);
  transition: border-color var(--dur-micro) ease, background-color var(--dur-micro) ease, transform var(--dur-impress) var(--ease-impress);
}
.menu-trigger:hover { border-color: var(--color-ink); }
.menu-trigger:active { transform: scale(0.96); }
.menu-trigger-icon {
  position: relative;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-ink);
  transition: transform 600ms var(--ease-spring);
}
.menu-trigger:hover .menu-trigger-icon { transform: scale(1.08); }
.menu-trigger-icon i {
  position: absolute;
  left: 7px;
  width: 10px;
  height: 1.5px;
  background: var(--color-bg);
  transition: transform var(--dur-sm) var(--ease-out-expo);
}
.menu-trigger-icon i:nth-child(1) { top: 9px; }
.menu-trigger-icon i:nth-child(2) { top: 13px; }
.menu-trigger:hover .menu-trigger-icon i:nth-child(1) { transform: translateX(-1px); }
.menu-trigger:hover .menu-trigger-icon i:nth-child(2) { transform: translateX(1px); }

/* 一页纸色的目录：墨迹遮罩从按钮处洇开 */
.menu-overlay {
  --menu-size: 0px;
  position: fixed;
  inset: 0;
  z-index: var(--z-menu);
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  color: var(--color-ink);
  overflow-y: auto;
  -webkit-mask-image: var(--ink-blot);
  mask-image: var(--ink-blot);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-size: var(--menu-size) var(--menu-size);
  mask-size: var(--menu-size) var(--menu-size);
  -webkit-mask-position: var(--menu-x, 100%) var(--menu-y, 0);
  mask-position: var(--menu-x, 100%) var(--menu-y, 0);
}
html.reduce-motion .menu-overlay { -webkit-mask-image: none; mask-image: none; }
/* 纸纹 */
.menu-overlay::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: calc(var(--grain-opacity) * 1.4);
  background-image: url("/textures/fiber-a.png"), url("/textures/fiber-b.png");
  background-size: 160px, 224px;
}
html[data-theme="dark"] .menu-overlay::before { filter: invert(1); mix-blend-mode: screen; }

.menu-head {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding-block: clamp(24px, 4vw, 48px) 20px;
  border-bottom: 1px solid var(--color-ink);
}
.menu-masthead { display: flex; flex-direction: column; gap: 8px; }
.menu-vol { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--color-ink-muted); }
.menu-heading {
  font-size: clamp(32px, 4vw, 56px);
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variation-settings: "opsz" 144, "SOFT" 60;
}
.menu-heading em { margin-left: 0.3em; font-family: var(--font-serif); font-style: normal; font-size: 0.42em; font-weight: 700; letter-spacing: 0.1em; color: var(--color-accent-text); vertical-align: 0.4em; }
.menu-close {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 6px 0 14px;
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-pill);
  transition: color var(--dur-micro) ease, border-color var(--dur-micro) ease;
}
.menu-close:hover { color: var(--color-ink); border-color: var(--color-ink); }
.menu-close-x { position: relative; width: 28px; height: 28px; border-radius: 50%; background: var(--color-seal); transition: transform 600ms var(--ease-spring); }
.menu-close:hover .menu-close-x { transform: rotate(90deg); }
.menu-close-x i { position: absolute; left: 8px; top: 13px; width: 12px; height: 1.5px; background: var(--color-bg); }
.menu-close-x i:nth-child(1) { transform: rotate(45deg); }
.menu-close-x i:nth-child(2) { transform: rotate(-45deg); }

.menu-list {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding-block: clamp(16px, 3vh, 40px);
}
.menu-link {
  position: relative;
  display: grid;
  grid-template-columns: 64px auto minmax(24px, 1fr) auto 96px;
  align-items: baseline;
  gap: 0 16px;
  padding-block: clamp(4px, 0.9vh, 10px);
  border-bottom: 1px solid var(--color-line);
  transition: opacity 400ms var(--ease-out-quart);
}
.menu-list:has(.menu-link:hover) .menu-link:not(:hover) { opacity: 0.32; }
.menu-index { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; color: var(--color-accent-text); }
.menu-line-mask { display: block; overflow: hidden; padding-bottom: 0.08em; }
.menu-line-inner {
  display: block;
  font-family: var(--font-serif);
  font-size: clamp(30px, 5.4vh, 64px);
  font-weight: 900;
  line-height: 1.08;
  letter-spacing: -0.02em;
  transition: transform 700ms var(--ease-out-expo), color var(--dur-sm) ease;
}
.menu-link:hover .menu-line-inner { transform: translateX(14px); }
.menu-link.is-current .menu-line-inner { color: var(--color-ink-muted); }
.menu-link.is-current .menu-index::after { content: " · 此页"; color: var(--color-ink-muted); }
.menu-link .leader { transform-origin: 0 50%; }
.menu-desc { font-family: var(--font-serif); font-size: 15px; color: var(--color-ink-muted); white-space: nowrap; }
.menu-page { font-family: var(--font-display); font-style: italic; font-size: 18px; text-align: right; color: var(--color-ink-muted); font-variation-settings: "opsz" 48, "SOFT" 100; }
.menu-link:hover .menu-page { color: var(--color-accent-text); }

.menu-foot {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding-block: 18px 28px;
  border-top: 1px solid var(--color-line);
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
}

@media (max-width: 860px) {
  .menu-link { grid-template-columns: 52px 1fr auto; }
  .menu-link .leader, .menu-desc { display: none; }
  .menu-page { font-size: 14px; }
}
@media (max-width: 520px) {
  .menu-trigger-label { display: none; }
  .menu-trigger { padding: 0 5px; }
  .menu-close kbd { display: none; }
}
</style>
