<script setup lang="ts">
import { PIGMENT_SWATCHES } from '~/utils/pigment';
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { Globe, Palette, ShieldCheck, Plug, RotateCcw, Save } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';
import { useLenis } from '~/composables/useLenis';

definePageMeta({ layout: 'admin' });
useHead({ title: '站点设置 · 编辑部后台' });

const toast = useToast();
const { confirm } = useConfirm();
const { scrollTo, getLenis } = useLenis();

const EDITABLE = ['site_title', 'subtitle', 'description', 'accent_color', 'icp', 'police_icp', 'diurnal_lighting'] as const;
type Form = { site_title: string; subtitle: string; description: string; accent_color: string; icp: string; police_icp: string; diurnal_lighting: boolean };

const form = ref<Form>({ site_title: '', subtitle: '', description: '', accent_color: PIGMENT_SWATCHES[0].hex, icp: '', police_icp: '', diurnal_lighting: true });
const original = ref<Form | null>(null);
const integrations = ref<Record<string, boolean>>({});
const loading = ref(true);
const saving = ref(false);

const changed = computed(() => (original.value ? EDITABLE.filter((k) => form.value[k] !== original.value![k]) : []));

const SECTIONS = [
  { id: 'basic', label: '基础信息', icon: Globe },
  { id: 'look', label: '外观', icon: Palette },
  { id: 'legal', label: '合规备案', icon: ShieldCheck },
  { id: 'integrations', label: '系统集成', icon: Plug },
];
const SWATCHES = PIGMENT_SWATCHES.map((p) => p.hex);
const SYSTEMS = [
  { key: 'cos', label: '腾讯云 COS', desc: '图片直传与 CDN 分发', on: '云端直传', off: '本地降级模式' },
  { key: 'github', label: 'GitHub API', desc: '项目星标与发布同步', on: '已配置令牌', off: '公开限额' },
  { key: 'smtp', label: 'SMTP 邮件', desc: '评论回复通知', on: '已配置', off: '未配置' },
];

async function load() {
  loading.value = true;
  try {
    const d = await adminFetch<any>('/api/v1/admin/settings');
    const next: Form = {
      site_title: d.site_title || '',
      subtitle: d.subtitle || '',
      description: d.description || '',
      accent_color: d.accent_color || PIGMENT_SWATCHES[0].hex,
      icp: d.icp || '',
      police_icp: d.police_icp || '',
      diurnal_lighting: !!d.diurnal_lighting,
    };
    form.value = next;
    original.value = { ...next };
    integrations.value = d.integrations || {};
  } catch (err) {
    toast.error('设置加载失败', apiErrorMessage(err));
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (!changed.value.length || saving.value) return;
  saving.value = true;
  try {
    const body = Object.fromEntries(changed.value.map((k) => [k, form.value[k]]));
    await adminFetch('/api/v1/admin/settings', { method: 'PATCH', body });
    original.value = { ...form.value };
    toast.success('设置已保存', `更新了 ${Object.keys(body).length} 项`);
  } catch (err) {
    toast.error('保存失败', apiErrorMessage(err));
  } finally {
    saving.value = false;
  }
}

async function discard() {
  if (!original.value) return;
  const ok = await confirm({ title: '放弃这些更改？', message: `${changed.value.length} 项修改将恢复为已保存的值。`, confirmText: '放弃更改', danger: true });
  if (ok) form.value = { ...original.value };
}

/* ---- 左侧目录：按滚动位置高亮当前分区 ----
 * 规则：顶部越过判定线（顶栏下方 120px）的最后一个分区为当前；滚到页面底部时取最后一个分区
 * （最后几个分区可能永远到不了判定线）。点击目录时立即选中目标，并在滚动动画期间暂停计算，
 * 避免高亮在途经的分区之间来回跳。
 */
const active = ref('basic');
let locked = false;
let lockTimer: ReturnType<typeof setTimeout> | undefined;
let spyTicking = false;

function lock() {
  locked = true;
  clearTimeout(lockTimer);
  lockTimer = setTimeout(checkUnlock, 1500);
}
/** 兜底解锁：Lenis 仍在执行这次平滑滚动就继续等，否则（动画被打断等）立即解锁 */
function checkUnlock() {
  const lenis = getLenis() as { isScrolling?: unknown } | null;
  if (locked && lenis?.isScrolling) {
    lockTimer = setTimeout(checkUnlock, 300);
    return;
  }
  unlock();
}
function unlock() {
  if (!locked) return;
  locked = false;
  clearTimeout(lockTimer);
  computeActive();
}
/** 用户自己动了滚轮 / 触摸 / 键盘，立即把控制权还给滚动位置 */
function onUserScrollIntent() {
  unlock();
}

function computeActive() {
  if (locked) return;
  const line = 120;
  const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
  if (atBottom) {
    active.value = SECTIONS[SECTIONS.length - 1].id;
    return;
  }
  let current = SECTIONS[0].id;
  for (const s of SECTIONS) {
    const el = document.getElementById(`sec-${s.id}`);
    if (el && el.getBoundingClientRect().top <= line) current = s.id;
  }
  active.value = current;
}

function onSpyScroll() {
  if (spyTicking) return;
  spyTicking = true;
  requestAnimationFrame(() => {
    spyTicking = false;
    computeActive();
  });
}

function go(id: string) {
  const el = document.getElementById(`sec-${id}`);
  if (!el) return;
  active.value = id;
  lock();
  if (getLenis()) {
    scrollTo(el, { offset: -84, onComplete: unlock });
  } else {
    window.addEventListener('scrollend', unlock, { once: true });
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 84, behavior: 'smooth' });
  }
}

function onKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    save();
  }
}
function onBeforeUnload(e: BeforeUnloadEvent) {
  if (changed.value.length) {
    e.preventDefault();
    e.returnValue = '';
  }
}
onBeforeRouteLeave(async () => {
  if (!changed.value.length) return true;
  return await confirm({ title: '离开设置页？', message: '还有未保存的更改，离开后将会丢失。', confirmText: '放弃并离开', danger: true });
});

onMounted(async () => {
  window.addEventListener('keydown', onKey);
  window.addEventListener('beforeunload', onBeforeUnload);
  window.addEventListener('scroll', onSpyScroll, { passive: true });
  window.addEventListener('resize', onSpyScroll, { passive: true });
  window.addEventListener('wheel', onUserScrollIntent, { passive: true });
  window.addEventListener('touchstart', onUserScrollIntent, { passive: true });
  await load();
  requestAnimationFrame(computeActive);
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey);
  window.removeEventListener('beforeunload', onBeforeUnload);
  window.removeEventListener('scroll', onSpyScroll);
  window.removeEventListener('resize', onSpyScroll);
  window.removeEventListener('wheel', onUserScrollIntent);
  window.removeEventListener('touchstart', onUserScrollIntent);
  window.removeEventListener('scrollend', unlock);
  clearTimeout(lockTimer);
});
</script>

<template>
  <div class="settings">
    <AdminPageHeader index="05" en="Settings" title="站点设置" description="全站基础信息、外观、备案与第三方集成状态。" />

    <div class="layout">
      <nav class="toc a-rise" style="--i: 1" aria-label="设置分区">
        <button v-for="s in SECTIONS" :key="s.id" type="button" class="toc-link" :class="{ 'is-on': active === s.id }" @click="go(s.id)">
          <component :is="s.icon" :size="15" :stroke-width="1.75" />{{ s.label }}
        </button>
      </nav>

      <div class="sections">
        <!-- 基础信息 -->
        <section id="sec-basic" class="a-card a-rise" style="--i: 2">
          <header class="a-card-head"><div><p class="a-card-title">基础信息</p><p class="a-card-sub">出现在浏览器标签、RSS 与搜索结果中</p></div></header>
          <div class="a-card-body body">
            <div class="a-field">
              <label class="a-label" for="st-title">站点名称 <small>{{ form.site_title.length }} / 60</small></label>
              <input id="st-title" v-model="form.site_title" class="a-input" type="text" maxlength="60" :disabled="loading">
            </div>
            <div class="a-field">
              <label class="a-label" for="st-sub">标语</label>
              <input id="st-sub" v-model="form.subtitle" class="a-input" type="text" maxlength="80" :disabled="loading">
            </div>
            <div class="a-field">
              <label class="a-label" for="st-desc">站点描述 <small :class="{ 'is-warn': form.description.length > 160 }">{{ form.description.length }} / 160</small></label>
              <textarea id="st-desc" v-model="form.description" class="a-textarea" rows="3" :disabled="loading" />
              <span class="meter" aria-hidden="true"><i :class="{ 'is-warn': form.description.length > 160 }" :style="{ transform: `scaleX(${Math.min(1, form.description.length / 160)})` }" /></span>
              <p class="a-hint">建议 80–160 字，超出部分会被搜索引擎截断。</p>
            </div>
            <div class="serp" aria-label="搜索结果预览">
              <p class="serp-label">搜索结果预览</p>
              <p class="serp-url a-mono">luntrix.com</p>
              <p class="serp-title">{{ form.site_title || '站点名称' }}<template v-if="form.subtitle"> · {{ form.subtitle }}</template></p>
              <p class="serp-desc">{{ form.description ? (form.description.length > 160 ? form.description.slice(0, 157) + '…' : form.description) : '站点描述会显示在这里。' }}</p>
            </div>
          </div>
        </section>

        <!-- 外观 -->
        <section id="sec-look" class="a-card a-rise" style="--i: 3">
          <header class="a-card-head"><div><p class="a-card-title">外观</p><p class="a-card-sub">强调色与四时光照</p></div></header>
          <div class="a-card-body body">
            <div class="a-field">
              <span class="a-label">全局强调色 <small>{{ form.accent_color }}</small></span>
              <div class="accent-row">
                <div class="swatches">
                  <button
                    v-for="c in SWATCHES"
                    :key="c"
                    type="button"
                    class="swatch"
                    :class="{ 'is-on': form.accent_color.toLowerCase() === c.toLowerCase() }"
                    :style="{ '--c': c }"
                    :aria-label="`使用 ${c}`"
                    @click="form.accent_color = c"
                  />
                </div>
                <span class="accent-sample" :style="{ '--c': form.accent_color }">
                  <span class="accent-btn">按钮样例</span>
                  <span class="accent-link">链接下划线</span>
                </span>
              </div>
            </div>
            <div class="flag">
              <div>
                <p class="flag-title">四时光照</p>
                <p class="a-hint">界面的纸色与强调色随访客当地时间（晨、昼、暮、夜）缓慢过渡</p>
              </div>
              <AdminSwitch v-model="form.diurnal_lighting" label="四时光照" :disabled="loading" />
            </div>
          </div>
        </section>

        <!-- 合规 -->
        <section id="sec-legal" class="a-card a-rise" style="--i: 4">
          <header class="a-card-head"><div><p class="a-card-title">合规备案</p><p class="a-card-sub">显示在页脚</p></div></header>
          <div class="a-card-body body row-2">
            <div class="a-field">
              <label class="a-label" for="st-icp">ICP 备案号</label>
              <input id="st-icp" v-model="form.icp" class="a-input is-mono" type="text" placeholder="粤ICP备00000000号" :disabled="loading">
            </div>
            <div class="a-field">
              <label class="a-label" for="st-police">公安联网备案号</label>
              <input id="st-police" v-model="form.police_icp" class="a-input is-mono" type="text" placeholder="公网安备00000000号" :disabled="loading">
            </div>
          </div>
        </section>

        <!-- 集成 -->
        <section id="sec-integrations" class="a-card a-rise" style="--i: 5">
          <header class="a-card-head"><div><p class="a-card-title">系统集成</p><p class="a-card-sub">通过服务端环境变量配置，这里只显示状态，不回显密钥</p></div></header>
          <div class="a-card-body systems">
            <div v-for="s in SYSTEMS" :key="s.key" class="system" :class="{ 'is-on': integrations[s.key] }">
              <span class="system-dot" aria-hidden="true" />
              <p class="system-name">{{ s.label }}</p>
              <p class="a-hint">{{ s.desc }}</p>
              <span class="a-status" :class="integrations[s.key] ? 'is-ok' : ''">{{ integrations[s.key] ? s.on : s.off }}</span>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 未保存更改：底部浮起的保存条 -->
    <Transition name="savebar">
      <div v-if="changed.length" class="savebar" role="status">
        <span class="savebar-dot" aria-hidden="true" />
        <span class="savebar-text">{{ changed.length }} 项未保存的更改</span>
        <button type="button" class="a-btn a-btn-sm a-btn-quiet" @click="discard"><RotateCcw :size="13" /> 放弃</button>
        <button type="button" class="a-btn a-btn-sm a-btn-accent" :disabled="saving" @click="save">
          <span v-if="saving" class="a-spin" /><Save v-else :size="13" /> 保存 <kbd class="a-kbd savebar-kbd">⌘S</kbd>
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 32px; align-items: start; }
.toc { position: sticky; top: calc(var(--a-top-h) + 28px); display: flex; flex-direction: column; gap: 2px; }
.toc-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 36px;
  padding: 0 12px;
  font-size: 13px;
  text-align: left;
  color: var(--color-ink-muted);
  border-radius: var(--a-radius-sm);
  transition: color 220ms ease, background-color 220ms ease;
}
.toc-link::before {
  content: "";
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 2px;
  border-radius: 2px;
  background: var(--color-accent);
  transform: scaleY(0);
  transition: transform 420ms var(--ease-spring);
}
.toc-link:hover { color: var(--color-ink); background: var(--a-hover); }
.toc-link.is-on { color: var(--color-ink); font-weight: 500; }
.toc-link.is-on::before { transform: scaleY(1); }

/* 底部留白足够让最后一个分区也能滚到判定线，目录高亮才能逐个经过每一节 */
.sections { display: flex; flex-direction: column; gap: 20px; max-width: 760px; padding-bottom: max(96px, calc(100vh - 400px)); }
.sections > section { scroll-margin-top: 90px; }
.body { display: flex; flex-direction: column; gap: 20px; }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.a-label small.is-warn { color: var(--a-warn); }
.meter { display: block; height: 2px; border-radius: 2px; background: var(--a-hover); overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--a-ok); transform-origin: 0 50%; transition: transform 300ms var(--ease-out-quart), background-color 200ms ease; }
.meter i.is-warn { background: var(--a-warn); }

/* 搜索结果预览 */
.serp { padding: 16px 18px; border-radius: var(--a-radius); background: var(--color-bg); border: 1px solid var(--color-line); }
.serp-label { margin-bottom: 10px; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--color-ink-faint); }
.serp-url { font-size: 12px; color: var(--color-ink-muted); }
.serp-title { margin-top: 3px; font-size: 18px; line-height: 1.35; color: var(--color-info); }
.serp-desc { margin-top: 4px; font-size: 13px; line-height: 1.6; color: var(--color-ink-muted); }

/* 强调色 */
.accent-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; }
.swatches { display: flex; flex-wrap: wrap; gap: 8px; }
.swatch {
  position: relative;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--c);
  box-shadow: inset 0 0 0 1px var(--color-line-strong);
  transition: transform 420ms var(--ease-spring), box-shadow 200ms ease;
}
.swatch:hover { transform: scale(1.1); }
.swatch.is-on { box-shadow: 0 0 0 2px var(--a-panel), 0 0 0 4px var(--c); }
.accent-sample { display: inline-flex; align-items: center; gap: 14px; }
.accent-btn {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--day-bg);
  border-radius: 999px;
  background: var(--c);
  transition: background-color 400ms ease;
}
.accent-link { font-family: var(--font-serif); font-size: 14px; text-decoration: underline; text-decoration-color: var(--c); text-decoration-thickness: 1.5px; text-underline-offset: 0.25em; }

.flag { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid var(--color-line); border-radius: var(--a-radius); }
.flag-title { font-size: 13.5px; font-weight: 600; }

/* 集成 */
.systems { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.system { position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 16px; border: 1px solid var(--color-line); border-radius: var(--a-radius); }
.system-dot { position: absolute; top: 18px; right: 16px; width: 8px; height: 8px; border-radius: 50%; background: var(--color-ink-faint); }
.system.is-on .system-dot { background: var(--a-ok); box-shadow: 0 0 0 4px color-mix(in oklab, var(--a-ok) 15%, transparent); }
.system-name { font-size: 13.5px; font-weight: 600; }
.system .a-status { margin-top: 6px; }

/* 保存条 */
.savebar {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 80;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 6px 6px 16px;
  transform: translateX(-50%);
  color: var(--color-ink);
  background: color-mix(in oklab, var(--color-bg) 86%, transparent);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-float), var(--edge-light);
  -webkit-backdrop-filter: blur(18px) saturate(1.6);
  backdrop-filter: blur(18px) saturate(1.6);
}
.savebar-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--a-warn); animation: pulse 1.8s ease-in-out infinite; }
@keyframes pulse { 50% { box-shadow: 0 0 0 5px color-mix(in oklab, var(--a-warn) 18%, transparent); } }
.savebar-text { margin-right: 6px; font-size: 13px; white-space: nowrap; }
.savebar-kbd { margin-left: 2px; color: inherit; opacity: 0.6; border-color: currentColor; }
.savebar-enter-active { transition: transform 620ms var(--ease-spring), opacity 260ms ease; }
.savebar-leave-active { transition: transform 260ms var(--ease-in-quart), opacity 200ms ease; }
.savebar-enter-from, .savebar-leave-to { opacity: 0; transform: translate(-50%, 24px) scale(0.96); }

@media (max-width: 960px) {
  .layout { grid-template-columns: 1fr; }
  .toc { position: static; flex-direction: row; overflow-x: auto; scrollbar-width: none; }
  .toc-link { flex-shrink: 0; }
  .toc-link::before { left: 12px; right: 12px; top: auto; bottom: 2px; width: auto; height: 2px; transform: scaleX(0); }
  .toc-link.is-on::before { transform: scaleX(1); }
  .systems { grid-template-columns: 1fr; }
  .row-2 { grid-template-columns: 1fr; }
}
@media (max-width: 1180px) and (min-width: 961px) {
  .systems { grid-template-columns: 1fr; }
}
</style>
