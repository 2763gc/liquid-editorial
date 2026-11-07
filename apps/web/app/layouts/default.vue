<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useTheme } from '~/composables/useTheme';
import { useLenis } from '~/composables/useLenis';
import { useMagnetic } from '~/composables/motion/useMagnetic';

const route = useRoute();
const theme = useTheme();
const { scrollTo } = useLenis();

const themeBtnRef = ref<HTMLElement | null>(null);
useMagnetic(themeBtnRef, 5);

/** 栏目编号与全屏菜单、PageMasthead 一致 */
const nav = [
  { label: '文章', path: '/posts' },
  { label: '专栏', path: '/series' },
  { label: '项目', path: '/projects' },
  { label: '归档', path: '/archive' },
  { label: '关于', path: '/about' },
];

const themeLabel = computed(() => ({ auto: '自动', light: '昼', dark: '夜' } as const)[theme.mode.value]);
const periodLabel = computed(() => ({ morning: '晨', day: '昼', dusk: '暮', night: '夜' } as const)[theme.period.value]);

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/');
}

/* ---- 导航：悬停底色在条目之间滑动；当前栏目的圆点随路由滑到新位置 ---- */
const navRef = ref<HTMLElement | null>(null);
const hover = ref({ x: 0, w: 0, on: false });
const dot = ref({ x: 0, on: false });
const navReady = ref(false);
let navRo: ResizeObserver | null = null;
let hoverTimer = 0;

function onNavEnter(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement;
  window.clearTimeout(hoverTimer);
  // 悬停意图：60ms 防抖，划过时不闪
  const go = () => { hover.value = { x: el.offsetLeft, w: el.offsetWidth, on: true }; };
  if (hover.value.on) go();
  else hoverTimer = window.setTimeout(go, 60);
}
function onNavLeave() {
  window.clearTimeout(hoverTimer);
  hover.value = { ...hover.value, on: false };
}
function placeDot() {
  const el = navRef.value?.querySelector<HTMLElement>('.site-nav-link.is-active');
  dot.value = el ? { x: el.offsetLeft + el.offsetWidth / 2, on: true } : { ...dot.value, on: false };
}
watch(() => route.path, () => nextTick(placeDot));

function onThemeClick(e: MouseEvent) {
  // 键盘触发的 click 没有坐标，交给 useTheme 用按钮中心
  theme.cycle(e.detail > 0 ? { x: e.clientX, y: e.clientY } : undefined);
}

/* ---- 顶栏：向下滚动隐藏、向上滚动出现（只读 scrollY，不在滚动回调里写布局） ---- */
const headerHidden = ref(false);
const headerScrolled = ref(false);
let lastY = 0;

function onScroll() {
  const y = window.scrollY;
  const delta = y - lastY;
  headerScrolled.value = y > 8;
  if (y < 120) headerHidden.value = false;
  else if (delta > 6) headerHidden.value = true;
  else if (delta < -6) headerHidden.value = false;
  lastY = y;
}

function onKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  if (e.key === 't' || e.key === 'T') theme.cycle();
}

/* ---- 页脚：本地时间与「已印行」天数（依赖时间，挂载后才计算） ---- */
const clock = ref('');
const days = ref<number | null>(null);
let clockTimer: number | undefined;
const SINCE = Date.UTC(2024, 0, 1);
function tickClock() {
  const d = new Date();
  clock.value = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  days.value = Math.floor((d.getTime() - SINCE) / 86400000);
}

function toTop() {
  scrollTo(0, { offset: 0, duration: 1.6 });
}

const year = new Date().getFullYear();
const WORD = 'LUNTRIX'.split('');

onMounted(() => {
  lastY = window.scrollY;
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('keydown', onKeydown);
  placeDot();
  // 首次定位不做动画，之后的路由切换才让圆点滑过去
  window.setTimeout(() => { navReady.value = true; }, 50);
  // 字体加载、跨断点缩放都会改变条目宽度，导航尺寸一变就重新定位
  navRo = new ResizeObserver(placeDot);
  if (navRef.value) navRo.observe(navRef.value);
  tickClock();
  clockTimer = window.setInterval(tickClock, 20000);
});
onBeforeUnmount(() => {
  window.removeEventListener('scroll', onScroll);
  window.removeEventListener('keydown', onKeydown);
  window.clearInterval(clockTimer);
  window.clearTimeout(hoverTimer);
  navRo?.disconnect();
});
</script>

<template>
  <div class="site">
    <a href="#main" class="skip-link">跳到正文</a>
    <!-- 加载：顶部一条走纸墨线 -->
    <NuxtLoadingIndicator color="var(--color-ink)" :height="1" :throttle="160" />
    <MotionCustomCursor />
    <MotionOpeningCurtain />
    <div class="paper-fiber" aria-hidden="true" />
    <div class="light-window" aria-hidden="true" />
    <InkDefs />

    <div class="site-sheet">
      <header class="site-header" :class="{ 'is-hidden': headerHidden, 'is-scrolled': headerScrolled }">
        <div class="site-header-inner page-shell">
          <NuxtLink to="/" class="site-logo" aria-label="Luntrix's Editorial，返回首页">
            <span class="site-logo-mark" aria-hidden="true" />
            <svg class="site-logo-word" viewBox="0 0 92 28" aria-hidden="true">
              <text class="logo-fill" x="0" y="21">Luntrix</text>
              <text class="logo-stroke" x="0" y="21">Luntrix</text>
            </svg>
            <span class="site-logo-sub">Editorial</span>
          </NuxtLink>

          <nav ref="navRef" class="site-nav" :class="{ 'is-ready': navReady }" aria-label="主导航" @mouseleave="onNavLeave">
            <span class="site-nav-hover" :class="{ 'is-on': hover.on }" :style="{ transform: `translate3d(${hover.x}px, 0, 0)`, width: `${hover.w}px` }" aria-hidden="true" />
            <NuxtLink
              v-for="item in nav"
              :key="item.path"
              :to="item.path"
              class="site-nav-link"
              :class="{ 'is-active': isActive(item.path) }"
              :aria-current="isActive(item.path) ? 'page' : undefined"
              @mouseenter="onNavEnter"
            >{{ item.label }}</NuxtLink>
            <span class="site-nav-dot" :class="{ 'is-on': dot.on }" :style="{ transform: `translate3d(${dot.x}px, 0, 0)` }" aria-hidden="true" />
          </nav>

          <div class="site-actions">
            <UiCommandPalette />
            <button
              ref="themeBtnRef"
              type="button"
              class="theme-toggle"
              :title="`主题：${themeLabel}（按 T 切换）`"
              :aria-label="`切换主题，当前为${themeLabel}`"
              @click="onThemeClick"
            >
              <span class="theme-dot" :data-mode="theme.mode.value" aria-hidden="true" />
              <span class="theme-text">
                <Transition name="swap" mode="out-in">
                  <span :key="theme.mode.value + periodLabel">{{ theme.mode.value === 'auto' ? `自动 · ${periodLabel}` : themeLabel }}</span>
                </Transition>
              </span>
            </button>
            <MotionFullScreenMenu />
          </div>
        </div>
      </header>

      <main id="main" class="site-main">
        <slot />
      </main>
      <!-- 页脚幕布的触发点：正文的下沿 -->
      <div class="footer-sentinel" aria-hidden="true" />
    </div>

    <footer class="site-footer">
      <div class="page-shell">
        <div class="footer-grid">
          <div class="footer-about">
            <p class="eyebrow">Liquid Editorial · Vol. {{ year }}</p>
            <p class="footer-blurb">一份关于软件工程、系统架构与数字美学的个人刊物。代码、终端与架构图在这里都是一等公民。</p>
            <a href="/rss.xml" target="_blank" rel="noopener" class="btn btn-sm footer-rss">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16" /><circle cx="5" cy="19" r="1.4" fill="currentColor" /></svg>
              订阅 RSS
            </a>
          </div>
          <nav class="footer-col" aria-label="页脚导航">
            <p class="eyebrow">目录</p>
            <NuxtLink to="/posts" class="link-draw">特稿</NuxtLink>
            <NuxtLink to="/series" class="link-draw">专栏</NuxtLink>
            <NuxtLink to="/projects" class="link-draw">项目</NuxtLink>
            <NuxtLink to="/til" class="link-draw">今日所学</NuxtLink>
            <NuxtLink to="/archive" class="link-draw">合订本</NuxtLink>
          </nav>
          <div class="footer-col">
            <p class="eyebrow">更多</p>
            <NuxtLink to="/about" class="link-draw">关于</NuxtLink>
            <NuxtLink to="/uses" class="link-draw">工具</NuxtLink>
            <NuxtLink to="/links" class="link-draw">友链</NuxtLink>
            <NuxtLink to="/search" class="link-draw">检索</NuxtLink>
            <a href="/atom.xml" target="_blank" rel="noopener" class="link-draw">Atom</a>
          </div>
          <div class="footer-col footer-status">
            <p class="eyebrow">此刻</p>
            <span class="footer-clock"><b>{{ clock || '--:--' }}</b> 本地时间</span>
            <span>时段 · {{ periodLabel }}</span>
            <span>主题 · {{ themeLabel }}</span>
            <span v-if="days !== null">已印行 {{ days.toLocaleString() }} 天</span>
          </div>
        </div>

        <div class="footer-bar">
          <span>© {{ year }} Luntrix</span>
          <span>内容采用 CC BY-NC-SA 4.0</span>
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener" class="link-draw">粤ICP备00000000号</a>
          <span>Built with Vue &amp; Python</span>
          <NuxtLink to="/admin" class="link-draw footer-admin">编辑部</NuxtLink>
          <button type="button" class="footer-top" @click="toTop">
            回到刊首 <i aria-hidden="true">↑</i>
          </button>
        </div>
      </div>
      <div class="footer-word" aria-hidden="true">
        <span v-for="(ch, i) in WORD" :key="i" class="footer-letter" :style="{ '--i': i }">{{ ch }}</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.site {
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  timeline-scope: --footer-reveal;
}

/* 正文是一张印好的纸：不透明、压在页脚之上；滚到底时被揭起，露出下层的页脚（M13） */
.site-sheet {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}
.footer-sentinel { height: 1px; margin-top: var(--space-32); view-timeline: --footer-reveal block; }

/* ---------------- 顶栏 ---------------- */
.site-header {
  position: sticky;
  top: 0;
  z-index: var(--z-header);
  height: var(--header-h);
  border-bottom: 1px solid transparent;
  transition:
    transform 640ms var(--ease-out-expo),
    background-color 400ms var(--ease-out-quart),
    border-color 400ms var(--ease-out-quart);
}
.site-header.is-scrolled {
  background: var(--color-paper-glass);
  border-bottom-color: var(--color-line);
  -webkit-backdrop-filter: blur(18px) saturate(1.6);
  backdrop-filter: blur(18px) saturate(1.6);
}
.site-header.is-hidden { transform: translate3d(0, -100%, 0); }
.site-header-inner {
  height: 100%;
  display: flex;
  align-items: center;
  gap: 32px;
}

/* 文字标：悬停时描边从字形轮廓上绘出（PRD 2.6），墨色在描边之下退成浅版 */
.site-logo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.site-logo-mark {
  width: 10px;
  height: 10px;
  background: var(--color-accent);
  transition: transform 800ms var(--ease-spring);
}
.site-logo:hover .site-logo-mark { transform: rotate(90deg) scale(0.86); }
.site-logo-word { width: 92px; height: 28px; overflow: visible; }
.site-logo-word text {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variation-settings: "opsz" 48, "SOFT" 40;
}
.logo-fill { fill: var(--color-ink); transition: fill-opacity 500ms var(--ease-out-quart); }
.logo-stroke {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 0.9;
  stroke-dasharray: 120;
  stroke-dashoffset: 120;
  transition: stroke-dashoffset 0ms;
}
.site-logo:hover .logo-fill { fill-opacity: 0.18; transition-duration: 300ms; }
.site-logo:hover .logo-stroke { stroke-dashoffset: 0; transition: stroke-dashoffset 900ms var(--ease-out-quart); }
html.reduce-motion .logo-stroke { display: none; }
.site-logo-sub {
  font-family: var(--font-display);
  font-style: italic;
  font-size: 15px;
  color: var(--color-ink-muted);
  transform: translateY(1px);
  transition: color var(--dur-sm) ease;
}
.site-logo:hover .site-logo-sub { color: var(--color-accent-text); }

.site-nav {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}
.site-nav-hover {
  position: absolute;
  top: 50%;
  left: 0;
  height: 32px;
  margin-top: -16px;
  border-radius: var(--radius-xs);
  background: color-mix(in oklab, var(--color-ink) 5.5%, transparent);
  opacity: 0;
  pointer-events: none;
  transition:
    transform 520ms var(--ease-spring),
    width 520ms var(--ease-spring),
    opacity var(--dur-micro) var(--ease-out-quart);
}
.site-nav-hover.is-on { opacity: 1; transition-duration: 520ms, 520ms, 500ms; }
.site-nav-link {
  position: relative;
  padding: 8px 13px;
  font-size: var(--fs-small);
  letter-spacing: 0.02em;
  color: var(--color-ink-muted);
  transition: color var(--dur-sm) var(--ease-out-quart);
}
.site-nav-link:hover,
.site-nav-link.is-active { color: var(--color-ink); }
.site-nav-link:active { transform: translateY(1px); }
.site-nav-dot {
  position: absolute;
  left: -2px;
  bottom: -4px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--color-accent);
  scale: 0;
  pointer-events: none;
}
.site-nav.is-ready .site-nav-dot { transition: transform 640ms var(--ease-spring), scale 420ms var(--ease-out-back); }
.site-nav-dot.is-on { scale: 1; }

.site-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 12px;
  border-radius: var(--radius-xs);
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
  transition: color var(--dur-micro) ease, background-color var(--dur-micro) ease;
}
.theme-toggle:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 5%, transparent); }
.theme-toggle:active .theme-dot { transform: scale(0.88); }
.theme-dot {
  position: relative;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid currentColor;
  overflow: hidden;
  transition: transform 700ms var(--ease-spring);
}
.theme-toggle:hover .theme-dot { transform: rotate(-30deg); }
.theme-dot::after {
  content: "";
  position: absolute;
  inset: 0;
  background: currentColor;
  transform: translateX(50%);
  transition: transform 600ms var(--ease-out-expo);
}
.theme-dot[data-mode="light"]::after { transform: translateX(100%); }
.theme-dot[data-mode="dark"]::after { transform: translateX(0); }
.theme-text { display: inline-block; min-width: 4.5em; text-align: left; overflow: hidden; }

.swap-enter-active, .swap-leave-active { transition: transform 360ms var(--ease-out-expo), opacity 240ms ease; }
.swap-enter-from { transform: translateY(70%); opacity: 0; }
.swap-leave-to { transform: translateY(-70%); opacity: 0; }
.theme-text > span { display: inline-block; }

@media (max-width: 960px) {
  .site-nav { display: none; }
  .site-actions { margin-left: auto; }
  .theme-text { display: none; }
}
@media (max-width: 480px) {
  .site-logo-sub { display: none; }
}

.site-main { flex: 1; }

/* ---------------- 页脚：固定在正文下层，正文滚走时如一张印好的纸被揭起 ---------------- */
.site-footer {
  position: relative;
  z-index: 0;
  border-top: 1px solid var(--color-line);
  background: var(--color-surface);
  /* clip 而非 hidden：不形成滚动容器，滚动驱动动画才能找到页面滚动 */
  overflow: clip;
}
@media (min-width: 861px) and (min-height: 760px) {
  .site-footer { position: sticky; bottom: 0; }
  /* 揭起时纸的下沿投下一道极淡的影子，提示「上层是一张纸」 */
  .site-sheet { box-shadow: 0 24px 48px -32px rgb(var(--shadow-rgb) / calc(0.35 * var(--shadow-k))); }
}
.footer-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) repeat(3, minmax(0, 1fr));
  gap: var(--space-12);
  padding-block: var(--space-16) var(--space-12);
}
.footer-blurb {
  margin-top: 16px;
  max-width: 30ch;
  font-family: var(--font-serif);
  font-size: 1.05rem;
  line-height: 1.85;
  color: var(--color-ink-muted);
}
.footer-rss { margin-top: 24px; }
.footer-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  font-size: var(--fs-small);
}
.footer-col .eyebrow { margin-bottom: 6px; }
.footer-status { color: var(--color-ink-muted); font-size: var(--fs-micro); }
.footer-clock { display: inline-flex; align-items: baseline; gap: 8px; }
.footer-clock b {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.02em;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums lining-nums;
}

.footer-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 24px;
  padding-block: 20px;
  border-top: 1px solid var(--color-line);
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
}
.footer-admin { color: var(--color-ink-muted); }
.footer-top {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-micro);
  color: var(--color-ink-muted);
  transition: color var(--dur-micro) ease;
}
.footer-top i {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  font-style: normal;
  border: 1px solid var(--color-line-strong);
  border-radius: 50%;
  transition: transform 600ms var(--ease-spring), background-color var(--dur-sm) ease, color var(--dur-sm) ease, border-color var(--dur-sm) ease;
}
.footer-top:hover { color: var(--color-ink); }
.footer-top:hover i { transform: translateY(-3px); background: var(--color-ink); border-color: var(--color-ink); color: var(--color-bg); }

.footer-word {
  display: flex;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 23.5vw;
  font-weight: 900;
  /* line-height < 1 时字形墨水上溢超出边框盒，会盖住上方 footer-bar 并拦截点击 */
  pointer-events: none;
  line-height: 0.74;
  letter-spacing: -0.065em;
  color: var(--color-ink);
  user-select: none;
  margin-bottom: -0.05em;
  font-variation-settings: "opsz" 144, "SOFT" 0;
}
.footer-letter { display: inline-block; }
/* 滚动驱动：正文下沿进入视口时，字母依次升起（不支持的浏览器保持静止） */
@supports (animation-timeline: view()) {
  html.motion-ready .footer-letter {
    animation: footer-rise linear both;
    animation-timeline: --footer-reveal;
    animation-range: entry calc(var(--i) * 3%) cover calc(30% + var(--i) * 4%);
  }
}
@keyframes footer-rise {
  from { transform: translate3d(0, 62%, 0); }
  to { transform: none; }
}

@media (max-width: 860px) {
  .footer-grid { grid-template-columns: 1fr 1fr; gap: var(--space-8) var(--space-6); }
  .footer-about { grid-column: 1 / -1; }
}
@media (max-width: 520px) {
  .footer-top { margin-left: 0; }
}
</style>
