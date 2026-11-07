<script setup lang="ts">
import '~/styles/admin.css';
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import {
  LayoutDashboard, FileText, Zap, Image, Link2, Settings2,
  ExternalLink, LogOut, Sun, Moon, Menu, PenLine, Search, PanelLeftClose, PanelLeftOpen, ShieldCheck, Clock,
} from 'lucide-vue-next';
import { useTheme, runThemeTransition } from '~/composables/useTheme';
import { adminFetch, adminLogout, adminUser, onAdminChannel, broadcastAdmin } from '~/composables/admin/useAdminApi';
import { useAdminCommands } from '~/composables/admin/useAdminCommands';

/**
 * 后台外壳 · 编辑部的案头
 * - 侧栏：栏目带编号（§ 00…），选中项左侧一道墨线，在条目之间弹簧滑动；可收成 64px 的窄栏（记住偏好）
 * - 顶栏：当前栏目名 + 面包屑；接口连通状态；检索（⌘K）；撰写
 * - 键盘：⌘K 命令面板，g d / g p / g t / g m / g l / g s / g a 跳转，n 新建特稿，[ 收起或展开侧栏
 * - 安全：30 分钟无操作自动退出（最后一分钟提示）；多个标签页共享活跃状态，任一处退出全部退出
 * - 页面之间不做转场；内容区只有极短的错峰入场
 */
const route = useRoute();
const router = useRouter();
const siteTheme = useTheme();
const commands = useAdminCommands();

interface NavItem { to: string; label: string; icon: typeof FileText; no: string; key: string; exact?: boolean }
const groups: Array<{ label: string; items: NavItem[] }> = [
  { label: '案头', items: [{ to: '/admin', label: '仪表盘', icon: LayoutDashboard, no: '00', key: 'd', exact: true }] },
  { label: '内容', items: [{ to: '/admin/posts', label: '特稿', icon: FileText, no: '01', key: 'p' }, { to: '/admin/til', label: '今日所学', icon: Zap, no: '02', key: 't' }] },
  { label: '素材', items: [{ to: '/admin/media', label: '媒体库', icon: Image, no: '03', key: 'm' }, { to: '/admin/links', label: '友链', icon: Link2, no: '04', key: 'l' }] },
  { label: '系统', items: [{ to: '/admin/settings', label: '站点设置', icon: Settings2, no: '05', key: 's' }, { to: '/admin/security', label: '安全', icon: ShieldCheck, no: '06', key: 'a' }] },
];
const flat = groups.flatMap((g) => g.items);

function isActive(item: NavItem) {
  return item.exact ? route.path === item.to : route.path === item.to || route.path.startsWith(item.to + '/');
}

const isBare = computed(() => !!route.meta.adminBare);
const current = computed(() => [...flat].reverse().find((i) => isActive(i)));

/** 面包屑：编辑部 / 栏目 / 子页 */
const crumbs = computed(() => {
  const list: Array<{ label: string; to?: string }> = [{ label: '编辑部', to: '/admin' }];
  const hit = current.value && current.value.to !== '/admin' ? current.value : null;
  if (hit) list.push({ label: hit.label, to: hit.to });
  if (hit && route.path !== hit.to) list.push({ label: route.params.id === 'new' ? '新建' : '编辑' });
  return list;
});

/* ---- 侧栏选中墨线：在条目之间弹簧滑动 ---- */
const navRef = ref<HTMLElement | null>(null);
const ind = ref({ y: 0, h: 0, on: false });
const indReady = ref(false);
let navRo: ResizeObserver | null = null;
function placeIndicator() {
  const el = navRef.value?.querySelector<HTMLElement>('.a-nav-link.is-active');
  ind.value = el ? { y: el.offsetTop, h: el.offsetHeight, on: true } : { ...ind.value, on: false };
}

/* ---- 窄栏 / 窄屏抽屉 ---- */
const rail = ref(false);
const navOpen = ref(false);
function toggleRail() {
  rail.value = !rail.value;
  try { localStorage.setItem('blog_admin_rail', rail.value ? '1' : '0'); } catch {}
  nextTick(placeIndicator);
}
watch(() => route.fullPath, () => {
  navOpen.value = false;
  nextTick(placeIndicator);
});

/* ---- 后台独立的明暗偏好（默认夜间），离开后台时还原前台主题 ---- */
const THEME_KEY = 'blog_admin_theme';
const adminTheme = ref<'dark' | 'light'>('dark');
function applyAdminTheme() {
  siteTheme.setOverride(adminTheme.value);
}
function toggleTheme(e?: MouseEvent) {
  const next = adminTheme.value === 'dark' ? 'light' : 'dark';
  const btn = document.querySelector<HTMLElement>('.a-theme-btn')?.getBoundingClientRect();
  const origin = e && e.detail > 0 ? { x: e.clientX, y: e.clientY } : btn ? { x: btn.left + btn.width / 2, y: btn.top + btn.height / 2 } : undefined;
  runThemeTransition(() => {
    adminTheme.value = next;
    try { localStorage.setItem(THEME_KEY, next); } catch {}
    applyAdminTheme();
  }, origin);
}

/* ---- 当前用户 ---- */
const me = adminUser;
const initial = computed(() => (me.value?.display_name || me.value?.username || 'L').trim().slice(0, 1).toUpperCase());

function logout() {
  return adminLogout('logout');
}

/* ---- 空闲自动退出：30 分钟无操作退出，最后一分钟在底部提示；各标签页共享活跃时间 ---- */
const IDLE_MS = 30 * 60_000;
const WARN_MS = 60_000;
const idleLeft = ref(0);
let lastActive = Date.now();
let lastShared = 0;
let idleTimer: number | undefined;
let offChannel: (() => void) | null = null;
function markActive() {
  const now = Date.now();
  lastActive = now;
  if (idleLeft.value) idleLeft.value = 0;
  if (now - lastShared > 15_000) {
    lastShared = now;
    broadcastAdmin({ type: 'activity', at: now });
  }
}
function checkIdle() {
  const left = IDLE_MS - (Date.now() - lastActive);
  if (left <= 0) {
    window.clearInterval(idleTimer);
    adminLogout('idle');
    return;
  }
  idleLeft.value = left <= WARN_MS ? Math.ceil(left / 1000) : 0;
}
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'wheel', 'touchstart'] as const;
function onVisible() {
  if (document.visibilityState === 'visible') checkIdle();
}

/* ---- 接口连通状态：每分钟探一次，断开时顶栏亮起提示 ---- */
const api = ref<'ok' | 'down' | 'unknown'>('unknown');
let healthTimer: number | undefined;
async function ping() {
  try {
    await $fetch('/api/v1/health', { timeout: 4000 });
    api.value = 'ok';
  } catch {
    api.value = 'down';
  }
}

/* ---- 键盘：g + 字母跳转，n 新建，[ 窄栏，⌘K 命令面板 ---- */
let gPending = 0;
function isTyping(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable || !!t.closest('.cm-editor'));
}
function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    commands.toggle();
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e) || commands.open.value) return;
  if (gPending && Date.now() - gPending < 900) {
    gPending = 0;
    const hit = flat.find((i) => i.key === e.key.toLowerCase());
    if (hit) {
      e.preventDefault();
      router.push(hit.to);
    }
    return;
  }
  if (e.key === 'g') gPending = Date.now();
  else if (e.key === 'n') router.push('/admin/posts/new');
  else if (e.key === '[') toggleRail();
}

commands.register('layout', [
  ...flat.map((i) => ({ id: `go-${i.key}`, group: '前往', label: i.label, hint: `g ${i.key}`, run: () => router.push(i.to) })),
  { id: 'new-post', group: '动作', label: '撰写新特稿', hint: 'n', run: () => router.push('/admin/posts/new') },
  { id: 'theme', group: '动作', label: '切换明暗', run: () => toggleTheme() },
  { id: 'rail', group: '动作', label: '收起 / 展开侧栏', hint: '[', run: toggleRail },
  { id: 'site', group: '动作', label: '在新窗口打开前台', run: () => window.open('/', '_blank', 'noopener') },
  { id: 'logout', group: '动作', label: '退出登录', run: logout },
  { id: 'logout-all', group: '动作', label: '退出全部设备', run: async () => { try { await adminFetch('/api/v1/admin/auth/logout-all', { method: 'POST' }); } catch {} adminLogout('logout'); } },
]);

onMounted(() => {
  try {
    adminTheme.value = localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark';
    rail.value = localStorage.getItem('blog_admin_rail') === '1';
  } catch {}
  applyAdminTheme();
  nextTick(placeIndicator);
  window.setTimeout(() => { indReady.value = true; }, 60);
  navRo = new ResizeObserver(placeIndicator);
  if (navRef.value) navRo.observe(navRef.value);
  if (!me.value) adminFetch('/api/v1/admin/auth/me').then((u) => { me.value = u; }).catch(() => {});
  for (const ev of ACTIVITY_EVENTS) window.addEventListener(ev, markActive, { passive: true, capture: true });
  document.addEventListener('visibilitychange', onVisible);
  idleTimer = window.setInterval(checkIdle, 5000);
  offChannel = onAdminChannel((msg) => {
    if (msg.type === 'activity') lastActive = Math.max(lastActive, msg.at);
    else if (msg.type === 'logout') navigateTo({ path: '/admin/login', query: { reason: msg.reason || 'logout' } });
  });
  ping();
  healthTimer = window.setInterval(ping, 60_000);
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  navRo?.disconnect();
  window.clearInterval(healthTimer);
  window.removeEventListener('keydown', onKeydown);
  for (const ev of ACTIVITY_EVENTS) window.removeEventListener(ev, markActive, { capture: true });
  document.removeEventListener('visibilitychange', onVisible);
  window.clearInterval(idleTimer);
  offChannel?.();
  commands.unregister('layout');
  // 去登录页时由登录页继续接管，避免先闪一下前台主题
  if (!router.currentRoute.value.path.startsWith('/admin')) siteTheme.setOverride(null);
});
</script>

<template>
  <div class="a-shell" :class="{ 'is-bare': isBare, 'nav-open': navOpen, 'is-rail': rail }">
    <aside class="a-side" aria-label="后台导航">
      <div class="a-brand-row">
        <NuxtLink to="/admin" class="a-brand" aria-label="编辑部首页">
          <span class="a-brand-seal" aria-hidden="true">编</span>
          <span class="a-brand-text">
            <span class="a-brand-word">Luntrix</span>
            <span class="a-brand-tag">编辑部 · Desk</span>
          </span>
        </NuxtLink>
        <button type="button" class="a-icon-btn a-rail-btn" :aria-label="rail ? '展开侧栏' : '收起侧栏'" :title="`${rail ? '展开' : '收起'}侧栏（[）`" @click="toggleRail">
          <PanelLeftOpen v-if="rail" :size="16" :stroke-width="1.5" />
          <PanelLeftClose v-else :size="16" :stroke-width="1.5" />
        </button>
      </div>

      <nav ref="navRef" class="a-nav" :class="{ 'is-ready': indReady }">
        <span
          class="a-nav-ind"
          :class="{ 'is-on': ind.on }"
          :style="{ transform: `translate3d(0, ${ind.y}px, 0)`, height: `${ind.h}px` }"
          aria-hidden="true"
        />
        <div v-for="g in groups" :key="g.label" class="a-nav-group">
          <p class="a-nav-label">{{ g.label }}</p>
          <NuxtLink
            v-for="item in g.items"
            :key="item.to"
            :to="item.to"
            class="a-nav-link"
            :class="{ 'is-active': isActive(item) }"
            :aria-current="isActive(item) ? 'page' : undefined"
            :title="rail ? `${item.label}（g ${item.key}）` : undefined"
          >
            <span class="a-nav-no">{{ item.no }}</span>
            <component :is="item.icon" class="a-nav-icon" :size="16" :stroke-width="1.5" />
            <span class="a-nav-text">{{ item.label }}</span>
            <span class="a-nav-key" aria-hidden="true">g {{ item.key }}</span>
          </NuxtLink>
        </div>
      </nav>

      <div class="a-side-foot">
        <div class="a-user">
          <span class="a-avatar" aria-hidden="true">
            <img v-if="me?.avatar_url" :src="me.avatar_url" alt="">
            <template v-else>{{ initial }}</template>
          </span>
          <span class="a-user-text">
            <span class="a-user-name">{{ me?.display_name || '编辑' }}</span>
            <span class="a-user-id">@{{ me?.username || 'admin' }}</span>
          </span>
        </div>
        <div class="a-side-actions">
          <button type="button" class="a-icon-btn a-theme-btn" :title="adminTheme === 'dark' ? '切换到昼间' : '切换到夜间'" :aria-label="adminTheme === 'dark' ? '切换到昼间' : '切换到夜间'" @click="toggleTheme">
            <Transition name="a-icon-swap" mode="out-in">
              <Sun v-if="adminTheme === 'dark'" key="sun" :size="16" :stroke-width="1.5" />
              <Moon v-else key="moon" :size="16" :stroke-width="1.5" />
            </Transition>
          </button>
          <a href="/" target="_blank" rel="noopener" class="a-icon-btn" title="访问前台" aria-label="访问前台"><ExternalLink :size="16" :stroke-width="1.5" /></a>
          <button type="button" class="a-icon-btn is-danger" title="退出登录" aria-label="退出登录" @click="logout"><LogOut :size="16" :stroke-width="1.5" /></button>
        </div>
      </div>
    </aside>

    <div class="a-scrim" aria-hidden="true" @click="navOpen = false" />

    <div class="a-main">
      <header v-if="!isBare" class="a-top">
        <button type="button" class="a-icon-btn a-menu-btn" aria-label="打开导航" @click="navOpen = true"><Menu :size="18" :stroke-width="1.5" /></button>
        <div class="a-top-title">
          <nav class="a-crumbs" aria-label="面包屑">
            <template v-for="(c, i) in crumbs" :key="i">
              <span v-if="i > 0" class="a-crumb-sep" aria-hidden="true">/</span>
              <NuxtLink v-if="c.to && i < crumbs.length - 1" :to="c.to" class="a-crumb">{{ c.label }}</NuxtLink>
              <span v-else class="a-crumb is-current">{{ c.label }}</span>
            </template>
          </nav>
        </div>
        <div class="a-top-actions">
          <span class="a-api" :class="`is-${api}`" :title="api === 'ok' ? '接口连通' : api === 'down' ? '接口无法连接' : '正在检查接口'">
            <i aria-hidden="true" />{{ api === 'down' ? '接口断开' : 'API' }}
          </span>
          <button type="button" class="a-search-btn" @click="commands.toggle()">
            <Search :size="14" :stroke-width="1.5" />
            <span>检索与命令</span>
            <kbd class="a-kbd">⌘K</kbd>
          </button>
          <NuxtLink to="/admin/posts/new" class="a-btn a-btn-sm a-btn-primary"><PenLine :size="14" :stroke-width="1.75" /> 撰写</NuxtLink>
        </div>
      </header>

      <main class="a-content">
        <slot />
      </main>
    </div>

    <Transition name="a-idle">
      <div v-if="idleLeft" class="a-idle" role="alert">
        <Clock :size="15" :stroke-width="1.75" />
        <span>长时间没有操作，<b>{{ idleLeft }}</b> 秒后将自动退出。</span>
        <button type="button" class="a-btn a-btn-sm" @click="markActive">继续工作</button>
      </div>
    </Transition>

    <AdminCommandPalette />
    <AdminToaster />
    <AdminConfirm />
  </div>
</template>

<style scoped>
.a-idle {
  position: fixed;
  left: 50%;
  bottom: 20px;
  z-index: 120;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 8px 8px 14px;
  font-size: 13px;
  color: var(--color-ink);
  background: var(--a-paper);
  border: 1px solid var(--color-line-strong);
  border-left: 2px solid var(--a-warn);
  border-radius: var(--a-radius);
  box-shadow: 0 18px 40px -20px rgb(var(--shadow-rgb) / calc(0.5 * var(--shadow-k)));
  transform: translateX(-50%);
}
.a-idle > svg { color: var(--a-warn); }
.a-idle b { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.a-idle-enter-active { transition: opacity var(--a-dur) ease, transform var(--a-dur-md) var(--ease-out-expo); }
.a-idle-leave-active { transition: opacity var(--a-dur) ease; }
.a-idle-enter-from { opacity: 0; transform: translate(-50%, 10px); }
.a-idle-leave-to { opacity: 0; }
@media (max-width: 560px) { .a-idle { left: 16px; right: 16px; transform: none; } .a-idle-enter-from { transform: translateY(10px); } }
.a-shell {
  display: grid;
  grid-template-columns: var(--a-side-w) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100dvh;
  font-family: var(--font-sans);
  color: var(--color-ink);
  background: var(--a-desk);
  transition: grid-template-columns var(--a-dur-md) var(--ease-out-expo);
}
.a-shell.is-rail { grid-template-columns: var(--a-rail-w) minmax(0, 1fr); }

/* ---------------- 侧栏 ---------------- */
.a-side {
  position: sticky;
  top: 0;
  z-index: 60;
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: 14px 10px 12px;
  overflow: hidden;
  background: var(--a-paper);
  border-right: 1px solid var(--color-line);
}
.a-brand-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 2px 4px 18px 6px; }
.a-brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
.a-brand-seal {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 900;
  color: var(--day-bg);
  background: var(--color-seal);
  border-radius: 3px;
  transform: rotate(-3deg);
  transition: transform 420ms var(--ease-out-back);
}
.a-brand:hover .a-brand-seal { transform: rotate(3deg) scale(1.04); }
.a-brand-text { display: flex; flex-direction: column; min-width: 0; line-height: 1.15; }
.a-brand-word {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.02em;
  font-variation-settings: "opsz" 48, "SOFT" 40;
}
.a-brand-tag { font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.14em; color: var(--color-ink-faint); white-space: nowrap; }

.a-nav {
  position: relative;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;
}
.a-nav-group + .a-nav-group { margin-top: 18px; }
.a-nav-label {
  padding: 0 10px 6px;
  font-family: var(--font-serif);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: var(--color-ink-faint);
  white-space: nowrap;
}
.a-nav-link {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 20px 18px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 10px;
  margin-bottom: 1px;
  font-size: 13.5px;
  color: var(--color-ink-muted);
  border-radius: var(--a-radius-sm);
  white-space: nowrap;
  transition: color var(--a-dur) var(--ease-out-quart), background-color var(--a-dur) ease;
}
.a-nav-link:not(.is-active):hover { color: var(--color-ink); background: var(--a-hover); }
.a-nav-link.is-active { color: var(--color-ink); font-weight: 600; }
.a-nav-no { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; color: var(--color-ink-faint); transition: color var(--a-dur) ease; }
.a-nav-link.is-active .a-nav-no { color: var(--color-accent-text); }
.a-nav-icon { flex-shrink: 0; transition: transform var(--a-dur-md) var(--ease-out-back); }
.a-nav-link:hover .a-nav-icon { transform: translateX(1px) scale(1.06); }
.a-nav-text { overflow: hidden; text-overflow: ellipsis; }
.a-nav-key { font-family: var(--font-mono); font-size: 10px; color: var(--color-ink-faint); opacity: 0; transition: opacity var(--a-dur) ease; }
.a-nav-link:hover .a-nav-key { opacity: 1; }
/* 选中：一张更白的纸 + 左侧一道墨线 */
.a-nav-ind {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  border-radius: var(--a-radius-sm);
  background: var(--a-press);
  opacity: 0;
  pointer-events: none;
}
.a-nav-ind::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--color-ink);
}
.a-nav-ind.is-on { opacity: 1; }
.a-nav.is-ready .a-nav-ind { transition: transform 420ms var(--ease-spring), height 420ms var(--ease-spring), opacity var(--a-dur) ease; }

.a-side-foot {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid var(--color-line);
}
.a-user { display: flex; align-items: center; gap: 10px; padding: 0 4px; min-width: 0; }
.a-avatar {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  overflow: hidden;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--color-bg);
  background: var(--color-ink);
  box-shadow: 0 0 0 2px var(--a-paper), 0 0 0 3px var(--color-line-strong);
}
.a-avatar img { width: 100%; height: 100%; object-fit: cover; }
.a-user-text { display: flex; flex-direction: column; min-width: 0; }
.a-user-name { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.a-user-id { font-family: var(--font-mono); font-size: 10.5px; color: var(--color-ink-faint); }
.a-side-actions { display: flex; gap: 2px; padding: 0 2px; }

/* 窄栏（仅宽屏）：只留图标 */
@media (min-width: 961px) {
  .is-rail .a-brand-text,
  .is-rail .a-nav-label,
  .is-rail .a-nav-text,
  .is-rail .a-nav-key,
  .is-rail .a-nav-no,
  .is-rail .a-user-text { display: none; }
  .is-rail .a-brand-row { flex-direction: column; gap: 10px; padding-inline: 0; }
  .is-rail .a-nav-link { grid-template-columns: 1fr; justify-items: center; padding: 0; }
  .is-rail .a-nav-group + .a-nav-group { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--color-line); }
  .is-rail .a-side-actions { flex-direction: column; align-items: center; }
  .is-rail .a-user { justify-content: center; }
}

.a-icon-swap-enter-active, .a-icon-swap-leave-active { transition: transform var(--a-dur-md) var(--ease-out-back), opacity var(--a-dur) ease; }
.a-icon-swap-enter-from { transform: rotate(-90deg) scale(0.6); opacity: 0; }
.a-icon-swap-leave-to { transform: rotate(90deg) scale(0.6); opacity: 0; }

/* ---------------- 主区 ---------------- */
.a-main { min-width: 0; display: flex; flex-direction: column; }
.a-top {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--a-top-h);
  padding: 0 clamp(18px, 2.6vw, 36px);
  background: color-mix(in oklab, var(--a-desk) 84%, transparent);
  border-bottom: 1px solid var(--color-line);
  -webkit-backdrop-filter: blur(14px) saturate(1.4);
  backdrop-filter: blur(14px) saturate(1.4);
}
.a-menu-btn { display: none; margin-left: -6px; }
.a-top-title { min-width: 0; }
.a-crumbs { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 13px; }
.a-crumb { color: var(--color-ink-faint); white-space: nowrap; transition: color var(--a-dur) ease; }
a.a-crumb:hover { color: var(--color-ink); }
.a-crumb.is-current { font-family: var(--font-serif); font-size: 14px; font-weight: 700; color: var(--color-ink); }
.a-crumb-sep { color: var(--color-line-strong); }
.a-top-actions { margin-left: auto; display: flex; align-items: center; gap: 10px; }

.a-api {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  color: var(--color-ink-faint);
}
.a-api i { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.a-api.is-ok i { background: var(--a-ok); }
.a-api.is-down { color: var(--a-danger); }
.a-api.is-down i { animation: a-api-pulse 1.4s var(--ease-out-quart) infinite; }
@keyframes a-api-pulse { 50% { box-shadow: 0 0 0 4px color-mix(in oklab, var(--a-danger) 18%, transparent); } }

.a-search-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 6px 0 10px;
  font-size: 12px;
  color: var(--color-ink-muted);
  background: var(--a-paper);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius-sm);
  transition: color var(--a-dur) ease, border-color var(--a-dur) ease;
}
.a-search-btn:hover { color: var(--color-ink); border-color: var(--color-line-strong); }
.a-search-btn span { min-width: 6em; text-align: left; }

.a-content {
  width: 100%;
  max-width: 1320px;
  padding: clamp(22px, 2.6vw, 36px) clamp(18px, 2.6vw, 36px) 80px;
}
.a-shell.is-bare .a-content { max-width: none; padding: 0; }

.a-scrim { display: none; }

/* ---------------- 窄屏：侧栏变成抽屉 ---------------- */
@media (max-width: 960px) {
  .a-shell, .a-shell.is-rail { grid-template-columns: minmax(0, 1fr); }
  .a-side {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(272px, 86vw);
    transform: translate3d(-102%, 0, 0);
    transition: transform var(--a-dur-lg) var(--ease-out-expo);
    box-shadow: var(--shadow-float);
  }
  .a-rail-btn { display: none; }
  .nav-open .a-side { transform: none; }
  .a-scrim {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 55;
    background: color-mix(in oklab, var(--a-desk) 55%, transparent);
    -webkit-backdrop-filter: blur(4px);
    backdrop-filter: blur(4px);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--a-dur-md) ease;
  }
  .nav-open .a-scrim { opacity: 1; pointer-events: auto; }
  .a-menu-btn { display: inline-grid; }
  .a-search-btn span, .a-api { display: none; }
}
</style>
