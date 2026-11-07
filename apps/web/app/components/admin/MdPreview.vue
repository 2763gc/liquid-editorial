<script setup lang="ts">
import '~/styles/md-themes.css';
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { ChevronDown, Download, FileText, FileCode2, FileDown, Check, Smartphone, Monitor } from 'lucide-vue-next';
import { MD_THEMES, DEFAULT_MD_THEME, getMdTheme, mdPaperClass, ensureMdThemeFont } from '~/utils/mdThemes';
import {
  DEFAULT_EXPORT_OPTIONS, mdHeadHtml, exportPdf, exportHtml, exportMarkdown,
  type MdDoc, type MdExportOptions,
} from '~/composables/admin/useMdExport';
import { useToast } from '~/composables/admin/useToast';

const props = defineProps<{
  html: string;
  markdown: string;
  title: string;
  subtitle?: string;
  number?: number | null;
  accent?: string;
  layoutVariant?: string;
  wordCount: number;
  readingMinutes: number;
}>();

const toast = useToast();

/* ---- 主题：悬停即预览，点击才应用；偏好记在本机 ---- */
const THEME_KEY = 'blog_md_theme';
const themeId = ref(DEFAULT_MD_THEME);
const hoverId = ref<string | null>(null);
const theme = computed(() => getMdTheme(hoverId.value || themeId.value));
const applied = computed(() => getMdTheme(themeId.value));

function applyTheme(id: string) {
  themeId.value = id;
  hoverId.value = null;
  pickerOpen.value = false;
  try { localStorage.setItem(THEME_KEY, id); } catch {}
}
watch(theme, (t) => ensureMdThemeFont(t));

/* ---- 版面宽度 ---- */
const width = ref<'article' | 'phone'>('article');
const widthOptions = [
  { value: 'article', label: '文章' },
  { value: 'phone', label: '手机' },
];
watch(width, (w) => { try { localStorage.setItem('blog_md_width', w); } catch {} });

/* ---- 标题区 ---- */
const today = (() => {
  const d = new Date();
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
})();
const docMeta = computed(() => ({
  title: props.title || '未命名文稿',
  subtitle: props.subtitle || '',
  kicker: `No. ${issueNo(props.number)} · ${applied.value.en}`,
  meta: `${today} · ${props.wordCount.toLocaleString()} 字 · 约 ${props.readingMinutes} 分钟`,
}));
const paperHtml = computed(() => mdHeadHtml({ ...docMeta.value, kicker: `No. ${issueNo(props.number)} · ${theme.value.en}` }) + props.html);
const paperClass = computed(() => [
  mdPaperClass(theme.value.id),
  theme.value.id === 'site' && props.layoutVariant === 'essay' ? 'prose-essay' : '',
]);
const paperStyle = computed(() => (theme.value.id === 'site' && props.accent ? { '--color-accent': props.accent } : undefined));

/* ---- 弹层：挂到 body 上用 fixed 定位，避免被预览栏的滚动容器裁切 ----
 * 主题画廊优先停靠在预览区左侧（盖住写作区），让纸面在悬停预览时完整可见；放不下时退回到按钮下方。
 */
const pickerOpen = ref(false);
const exportOpen = ref(false);
const rootRef = ref<HTMLElement | null>(null);
const pickerBtn = ref<HTMLElement | null>(null);
const exportBtn = ref<HTMLElement | null>(null);
const pickerPop = ref<HTMLElement | null>(null);
const exportPop = ref<HTMLElement | null>(null);
const pickerPos = ref<Record<string, string>>({});
const exportPos = ref<Record<string, string>>({});

function place() {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (pickerOpen.value && pickerBtn.value && rootRef.value) {
    const btn = pickerBtn.value.getBoundingClientRect();
    const pane = rootRef.value.getBoundingClientRect();
    const w = Math.min(540, vw - 24);
    const top = btn.bottom + 8;
    const left = pane.left - w - 12 >= 12 ? pane.left - w - 12 : Math.max(12, Math.min(btn.left, vw - w - 12));
    pickerPos.value = { top: `${top}px`, left: `${left}px`, width: `${w}px`, maxHeight: `${vh - top - 16}px` };
  }
  if (exportOpen.value && exportBtn.value) {
    const btn = exportBtn.value.getBoundingClientRect();
    const w = 340;
    exportPos.value = { top: `${btn.bottom + 8}px`, left: `${Math.max(12, Math.min(btn.right - w, vw - w - 12))}px`, width: `${w}px` };
  }
}
watch([pickerOpen, exportOpen], () => nextTick(place));

function onDocDown(e: MouseEvent) {
  const t = e.target as Node;
  if (pickerOpen.value && !pickerPop.value?.contains(t) && !pickerBtn.value?.contains(t)) {
    pickerOpen.value = false;
    hoverId.value = null;
  }
  if (exportOpen.value && !exportPop.value?.contains(t) && !exportBtn.value?.contains(t)) exportOpen.value = false;
}
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape') return;
  if (pickerOpen.value) { pickerOpen.value = false; hoverId.value = null; }
  exportOpen.value = false;
}

/* ---- 导出 ---- */
const EXPORT_KEY = 'blog_md_export';
const opts = ref<MdExportOptions>({ ...DEFAULT_EXPORT_OPTIONS });
watch(opts, (v) => { try { localStorage.setItem(EXPORT_KEY, JSON.stringify(v)); } catch {} }, { deep: true });
const exporting = ref<'' | 'pdf' | 'html' | 'md'>('');

function currentDoc(): MdDoc {
  return {
    themeId: themeId.value,
    ...docMeta.value,
    html: props.html,
    markdown: props.markdown,
    accent: props.accent,
    essay: props.layoutVariant === 'essay',
  };
}

async function run(kind: 'pdf' | 'html' | 'md') {
  if (exporting.value) return;
  exporting.value = kind;
  try {
    if (kind === 'pdf') {
      await exportPdf(currentDoc(), opts.value);
    } else if (kind === 'html') {
      await exportHtml(currentDoc(), opts.value);
      toast.success('已导出 HTML', '单文件，样式与字体已内嵌，可直接分享或二次打印');
    } else {
      exportMarkdown(currentDoc());
      toast.success('已导出 Markdown', '标题与副标题已写入文件开头');
    }
    exportOpen.value = false;
  } catch {
    toast.error('导出失败', '请稍后重试');
  } finally {
    exporting.value = '';
  }
}

const PAPERS: Array<{ value: MdExportOptions['paper']; label: string }> = [
  { value: 'A4', label: 'A4' },
  { value: 'A5', label: 'A5' },
  { value: 'Letter', label: 'Letter' },
];
const MARGIN_OPTS: Array<{ value: MdExportOptions['margin']; label: string }> = [
  { value: 'narrow', label: '窄' },
  { value: 'normal', label: '标准' },
  { value: 'wide', label: '宽' },
];

onMounted(() => {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved && MD_THEMES.some((t) => t.id === saved)) themeId.value = saved;
    if (localStorage.getItem('blog_md_width') === 'phone') width.value = 'phone';
    const o = JSON.parse(localStorage.getItem(EXPORT_KEY) || 'null');
    if (o) opts.value = { ...DEFAULT_EXPORT_OPTIONS, ...o };
  } catch {}
  ensureMdThemeFont(theme.value);
  document.addEventListener('mousedown', onDocDown);
  window.addEventListener('keydown', onKey);
  window.addEventListener('resize', place);
});
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocDown);
  window.removeEventListener('keydown', onKey);
  window.removeEventListener('resize', place);
});
</script>

<template>
  <div ref="rootRef" class="pv">
    <!-- 预览工具栏 -->
    <div class="pv-bar">
      <div class="pv-wrap">
        <button ref="pickerBtn" type="button" class="pv-theme-btn" :class="{ 'is-open': pickerOpen }" :aria-expanded="pickerOpen" @click="pickerOpen = !pickerOpen">
          <span class="pv-swatch" aria-hidden="true">
            <i v-for="(c, i) in applied.swatch" :key="i" :style="{ background: c }" />
          </span>
          <span class="pv-theme-name">{{ applied.name }}</span>
          <span class="pv-theme-en">{{ applied.en }}</span>
          <ChevronDown :size="14" class="pv-chev" />
        </button>

        <Teleport to="body">
        <Transition name="pv-pop">
          <div v-if="pickerOpen" ref="pickerPop" class="pv-pop pv-picker" :style="pickerPos" data-lenis-prevent @mouseleave="hoverId = null">
            <header class="pv-pop-head">
              <span>排版主题</span>
              <small>悬停预览 · 点击应用</small>
            </header>
            <div class="pv-grid">
              <button
                v-for="t in MD_THEMES"
                :key="t.id"
                type="button"
                class="pv-card"
                :class="{ 'is-on': t.id === themeId }"
                :aria-pressed="t.id === themeId"
                @mouseenter="hoverId = t.id"
                @focus="hoverId = t.id"
                @click="applyTheme(t.id)"
              >
                <span class="pv-sample">
                  <span class="pv-sample-paper" :class="mdPaperClass(t.id)" :data-code="t.code">
                    <h2>章节标题</h2>
                    <p>正文段落，<strong>重点内容</strong>与 <code>inline</code> 代码。</p>
                    <blockquote><p>引用：好的排版让人忘记排版。</p></blockquote>
                  </span>
                  <span v-if="t.id === themeId" class="pv-check"><Check :size="12" :stroke-width="3" /></span>
                </span>
                <span class="pv-card-name"><b>{{ t.name }}</b><em>{{ t.en }}</em></span>
                <span class="pv-card-desc">{{ t.desc }}</span>
                <span class="pv-card-tags"><span v-for="tag in t.tags" :key="tag">{{ tag }}</span></span>
              </button>
            </div>
          </div>
        </Transition>
        </Teleport>
      </div>

      <UiSegmented v-model="width" :options="widthOptions" size="sm" aria-label="版面宽度" class="pv-width" />

      <div class="pv-wrap pv-wrap-right">
        <button ref="exportBtn" type="button" class="a-btn a-btn-sm" :class="{ 'is-on': exportOpen }" @click="exportOpen = !exportOpen">
          <Download :size="14" :stroke-width="2" /> 导出
        </button>

        <Teleport to="body">
        <Transition name="pv-pop">
          <div v-if="exportOpen" ref="exportPop" class="pv-pop pv-export" :style="exportPos">
            <header class="pv-pop-head">
              <span>导出文稿</span>
              <small>使用「{{ applied.name }}」主题</small>
            </header>
            <div class="pv-opts">
              <div class="pv-opt">
                <span>纸张</span>
                <span class="pv-seg">
                  <button v-for="p in PAPERS" :key="p.value" type="button" :class="{ 'is-on': opts.paper === p.value }" @click="opts.paper = p.value">{{ p.label }}</button>
                </span>
              </div>
              <div class="pv-opt">
                <span>页边距</span>
                <span class="pv-seg">
                  <button v-for="m in MARGIN_OPTS" :key="m.value" type="button" :class="{ 'is-on': opts.margin === m.value }" @click="opts.margin = m.value">{{ m.label }}</button>
                </span>
              </div>
              <div class="pv-opt">
                <span>页码</span>
                <AdminSwitch v-model="opts.pageNumbers" label="页码" />
              </div>
              <div class="pv-opt">
                <span>包含标题区</span>
                <AdminSwitch v-model="opts.includeTitle" label="包含标题区" />
              </div>
            </div>
            <div class="pv-actions">
              <button type="button" class="pv-action is-primary" :disabled="!!exporting" @click="run('pdf')">
                <span v-if="exporting === 'pdf'" class="a-spin" /><FileDown v-else :size="17" :stroke-width="1.75" />
                <span><b>PDF</b><small>矢量文字，适合打印与归档</small></span>
              </button>
              <button type="button" class="pv-action" :disabled="!!exporting" @click="run('html')">
                <FileCode2 :size="17" :stroke-width="1.75" />
                <span><b>HTML</b><small>单文件网页，样式内嵌</small></span>
              </button>
              <button type="button" class="pv-action" :disabled="!!exporting" @click="run('md')">
                <FileText :size="17" :stroke-width="1.75" />
                <span><b>Markdown</b><small>源文件 .md</small></span>
              </button>
            </div>
            <p class="pv-note">PDF 会打开打印窗口：目标打印机选择「另存为 PDF」，并在「更多设置」中勾选「背景图形」，纸色与代码底色才会保留。</p>
          </div>
        </Transition>
        </Teleport>
      </div>
    </div>

    <!-- 桌面与纸面 -->
    <div class="pv-stage" :class="`is-${width}`">
      <span class="pv-device" aria-hidden="true"><Smartphone v-if="width === 'phone'" :size="12" /><Monitor v-else :size="12" />{{ width === 'phone' ? '375 · 手机' : '760 · 文章' }}</span>
      <article
        class="pv-paper"
        :class="paperClass"
        :data-code="theme.code"
        :style="paperStyle"
        v-html="paperHtml"
      />
    </div>
  </div>
</template>

<style scoped>
.pv { min-height: 100%; display: flex; flex-direction: column; }

/* ---------------- 工具栏 ---------------- */
.pv-bar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 48px;
  padding: 0 14px;
  background: color-mix(in oklab, var(--color-bg) 86%, transparent);
  border-bottom: 1px solid var(--color-line);
  -webkit-backdrop-filter: blur(14px) saturate(1.4);
  backdrop-filter: blur(14px) saturate(1.4);
}
.pv-wrap { position: relative; }
.pv-wrap-right { margin-left: auto; }
.pv-width { margin-left: auto; }
.pv-wrap-right .a-btn.is-on { background: var(--a-press); }

.pv-theme-btn {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  height: 32px;
  padding: 0 10px 0 8px;
  font-size: 13px;
  color: var(--color-ink);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius-sm);
  transition: border-color 200ms ease, background-color 200ms ease;
}
.pv-theme-btn:hover, .pv-theme-btn.is-open { border-color: var(--color-line-strong); background: var(--a-hover); }
.pv-swatch { display: inline-flex; }
.pv-swatch i {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  box-shadow: 0 0 0 1.5px var(--a-panel), inset 0 0 0 1px rgb(0 0 0 / 0.12);
}
.pv-swatch i + i { margin-left: -5px; }
.pv-theme-name { font-weight: 600; }
.pv-theme-en { font-family: var(--font-display); font-style: italic; font-size: 12.5px; color: var(--color-ink-faint); }
.pv-chev { color: var(--color-ink-faint); transition: transform 400ms var(--ease-spring); }
.is-open .pv-chev { transform: rotate(180deg); }

/* ---------------- 弹层 ---------------- */
.pv-pop {
  position: fixed;
  z-index: 1100;
  color: var(--color-ink);
  font-family: var(--font-sans);
  background: color-mix(in oklab, var(--color-bg) 96%, transparent);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-float), var(--edge-light);
  -webkit-backdrop-filter: blur(20px) saturate(1.5);
  backdrop-filter: blur(20px) saturate(1.5);
}
.pv-pop-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 10px;
  font-size: 13.5px;
  font-weight: 600;
}
.pv-pop-head small { font-size: 11.5px; font-weight: 400; color: var(--color-ink-faint); }
.pv-pop-enter-active { transition: opacity 200ms ease, transform 460ms var(--ease-spring); transform-origin: 20% 0; }
.pv-pop-leave-active { transition: opacity 140ms ease, transform 160ms var(--ease-in-quart); }
.pv-pop-enter-from, .pv-pop-leave-to { opacity: 0; transform: translate3d(0, -6px, 0) scale(0.97); }

/* 主题画廊 */
.pv-picker { overflow-y: auto; overscroll-behavior: contain; }
.pv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 4px 14px 14px; }
.pv-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 6px 10px;
  text-align: left;
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  transition: border-color 200ms ease, background-color 200ms ease, transform 500ms var(--ease-spring), box-shadow 300ms ease;
}
.pv-card:hover { border-color: var(--color-line-strong); background: var(--a-hover); transform: translateY(-2px); }
.pv-card.is-on { border-color: var(--color-accent); box-shadow: 0 0 0 3px color-mix(in oklab, var(--color-accent) 15%, transparent); }
.pv-sample {
  position: relative;
  display: block;
  height: 112px;
  margin-bottom: 6px;
  overflow: hidden;
  border-radius: var(--a-radius-sm);
  box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.06);
}
/* 用真实主题样式渲染一小段样稿，再整体缩小一半 */
.pv-sample-paper {
  display: block;
  width: 200%;
  height: 200%;
  padding: 18px 22px;
  transform: scale(0.5);
  transform-origin: 0 0;
  font-size: 15px !important;
  pointer-events: none;
}
.pv-sample-paper > :first-child { margin-top: 0 !important; }
.pv-sample-paper.md-site { font-size: 17px !important; }
.pv-check {
  position: absolute;
  top: 6px;
  right: 6px;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: var(--day-bg);
  background: var(--color-accent);
  box-shadow: 0 2px 6px rgb(0 0 0 / 0.2);
}
.pv-card-name { display: flex; align-items: baseline; gap: 6px; padding: 0 4px; }
.pv-card-name b { font-size: 13.5px; }
.pv-card-name em { font-family: var(--font-display); font-size: 12px; color: var(--color-ink-faint); }
.pv-card-desc { padding: 0 4px; font-size: 11.5px; line-height: 1.5; color: var(--color-ink-muted); }
.pv-card-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; padding: 0 4px; }
.pv-card-tags span { padding: 1px 6px; font-size: 10px; color: var(--color-ink-faint); border: 1px solid var(--color-line); border-radius: 99px; }

/* 导出面板 */
.pv-opts { display: flex; flex-direction: column; padding: 0 16px 6px; }
.pv-opt { display: flex; align-items: center; justify-content: space-between; gap: 12px; height: 42px; font-size: 13px; }
.pv-opt + .pv-opt { border-top: 1px solid var(--color-line); }
.pv-seg { display: inline-flex; padding: 2px; border: 1px solid var(--color-line); border-radius: var(--a-radius-sm); }
.pv-seg button { height: 24px; padding: 0 10px; font-size: 12px; color: var(--color-ink-muted); border-radius: var(--a-radius-sm); transition: color 160ms ease, background-color 200ms ease; }
.pv-seg button:hover { color: var(--color-ink); }
.pv-seg button.is-on { color: var(--color-bg); background: var(--color-ink); }
.pv-actions { display: flex; flex-direction: column; gap: 6px; padding: 8px 10px 4px; }
.pv-action {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  text-align: left;
  color: var(--color-ink);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  transition: border-color 200ms ease, background-color 200ms ease, transform 420ms var(--ease-spring);
}
.pv-action:hover { border-color: var(--color-line-strong); background: var(--a-hover); }
.pv-action:active { transform: scale(0.98); }
.pv-action[disabled] { opacity: 0.6; pointer-events: none; }
.pv-action span { display: flex; flex-direction: column; gap: 1px; }
.pv-action b { font-size: 13px; }
.pv-action small { font-size: 11.5px; color: var(--color-ink-faint); }
.pv-action.is-primary { border-color: color-mix(in oklab, var(--color-accent) 50%, transparent); background: color-mix(in oklab, var(--color-accent) 8%, transparent); }
.pv-action.is-primary svg { color: var(--color-accent); }
.pv-note { padding: 8px 16px 14px; font-size: 11.5px; line-height: 1.6; color: var(--color-ink-faint); }

/* ---------------- 桌面与纸面 ---------------- */
.pv-stage {
  position: relative;
  flex: 1;
  padding: 36px clamp(16px, 3vw, 40px) 120px;
  background:
    radial-gradient(circle at 1px 1px, color-mix(in oklab, var(--color-ink) 7%, transparent) 1px, transparent 0) 0 0 / 18px 18px,
    var(--color-bg);
}
.pv-device {
  position: absolute;
  top: 12px;
  left: 50%;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transform: translateX(-50%);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--color-ink-faint);
}
.pv-paper {
  max-width: 760px;
  margin: 0 auto;
  padding: 56px clamp(24px, 4vw, 60px) 72px;
  border-radius: var(--a-radius-sm);
  box-shadow: 0 1px 2px rgb(0 0 0 / 0.06), 0 18px 48px -24px rgb(0 0 0 / 0.35), 0 0 0 1px rgb(0 0 0 / 0.04);
  transition: max-width 600ms var(--ease-out-expo), padding 600ms var(--ease-out-expo), border-radius 600ms var(--ease-out-expo), background-color 360ms ease, color 360ms ease;
}
.is-phone .pv-paper {
  max-width: 390px;
  padding: 36px 22px 56px;
  border-radius: 28px;
  box-shadow: 0 0 0 8px var(--night-surface), 0 0 0 9px var(--night-surface-2), 0 30px 60px -24px rgb(var(--shadow-rgb) / calc(0.5 * var(--shadow-k)));
}

@media (max-width: 1280px) {
  .pv-theme-en { display: none; }
}
@media (max-width: 560px) {
  .pv-grid { grid-template-columns: 1fr; }
}
</style>
