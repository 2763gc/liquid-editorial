<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import {
  ArrowLeft, SlidersHorizontal, Send, Save, ImagePlus, Bold, Italic, Code, Link2,
  Quote, Heading2, List, ListOrdered, SquareCode, Upload, FileUp, Maximize2, Minimize2, History,
} from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';
import { useDraftStore, type DraftPayload, type Revision } from '~/composables/admin/useDraftStore';
import { PIGMENT_SWATCHES, pigmentFor } from '~/utils/pigment';
import { variantForLayout } from '~/utils/inkArt';

interface EditorApi {
  wrap: (before: string, after?: string, placeholder?: string) => void;
  prefixLines: (prefix: (i: number) => string) => void;
  insert: (text: string) => void;
  focus: () => void;
}

// 固定 key：新建保存后地址从 /new 变成 /:id 时复用同一实例，不重新挂载整个编辑器
definePageMeta({ layout: 'admin', adminBare: true, key: 'admin-post-editor' });

const route = useRoute();
const router = useRouter();
const toast = useToast();
const { confirm } = useConfirm();

const postId = computed(() => String(route.params.id));
const isNew = computed(() => postId.value === 'new');

/* ---------------- 文稿状态 ---------------- */
const title = ref('');
const subtitle = ref('');
const slug = ref('');
const contentMd = ref('');
const layoutVariant = ref('standard');
const accentColor = ref(PIGMENT_SWATCHES[0].hex);
const status = ref<'draft' | 'published'>('draft');
const tagIds = ref<number[]>([]);
const isFeatured = ref(false);
const isPinned = ref(false);
const number = ref<number | null>(null);

const availableTags = ref<any[]>([]);
const loaded = ref(false);
const saving = ref<'' | 'save' | 'publish'>('');
const lastSavedAt = ref('');
const settingsOpen = ref(false);

useHead({ title: computed(() => `${title.value || (isNew.value ? '新特稿' : '编辑')} · 编辑部后台`) });

function payload() {
  return {
    title: title.value.trim(),
    subtitle: subtitle.value.trim(),
    slug: slug.value.trim() || undefined,
    content_md: contentMd.value,
    layout_variant: layoutVariant.value,
    accent_color: accentColor.value,
    tag_ids: [...tagIds.value].sort((a, b) => a - b),
    is_featured: isFeatured.value,
    is_pinned: isPinned.value,
  };
}
const snapshot = ref('');
const dirty = computed(() => loaded.value && JSON.stringify(payload()) !== snapshot.value);
function markClean() {
  snapshot.value = JSON.stringify(payload());
}

/* ---------------- 统计与光标 ---------------- */
const wordCount = computed(() => {
  const zh = (contentMd.value.match(/[一-龥]/g) || []).length;
  const en = (contentMd.value.match(/\b[a-zA-Z]+\b/g) || []).length;
  return zh + en;
});
const readingMinutes = computed(() => Math.max(1, Math.round(wordCount.value / 350)));
const caret = ref({ line: 1, col: 1 });

const saveLabel = computed(() => {
  if (saving.value) return saving.value === 'publish' ? '发布中…' : '保存中…';
  if (dirty.value) return '有未保存的更改';
  if (lastSavedAt.value) return `已保存 · ${lastSavedAt.value}`;
  return isNew.value ? '尚未保存' : '已同步';
});

/* ---------------- 视图模式 ---------------- */
type View = 'write' | 'split' | 'preview';
const view = ref<View>('split');
const viewOptions = [
  { value: 'write', label: '写作' },
  { value: 'split', label: '分栏' },
  { value: 'preview', label: '预览' },
];
watch(view, (v) => {
  try { localStorage.setItem('blog_editor_view', v); } catch {}
  nextTick(resizeSource);
});

/* ---------------- 实时预览：交给服务端，与前台文章页同一个渲染器（浏览器不下载 Shiki） ---------------- */
const previewHtml = ref('');
const previewing = ref(false);
const previewFailed = ref(false);
let previewTimer: ReturnType<typeof setTimeout> | undefined;
let previewSeq = 0;
async function renderPreview() {
  const seq = ++previewSeq;
  previewing.value = true;
  try {
    const res = await adminFetch<{ html: string }>('/api/content/preview', { method: 'POST', body: { markdown: contentMd.value || '' } });
    if (seq !== previewSeq) return;
    previewHtml.value = res.html;
    previewFailed.value = false;
  } catch (err) {
    // 连续失败只提示一次，不在每次敲键时刷屏
    if (seq === previewSeq && !previewFailed.value) toast.error('预览暂时渲染不出来', apiErrorMessage(err));
    if (seq === previewSeq) previewFailed.value = true;
  } finally {
    if (seq === previewSeq) previewing.value = false;
  }
}
watch(contentMd, () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(renderPreview, 260);
});

/* ---------------- 编辑区 ---------------- */
const editorRef = ref<EditorApi | null>(null);
const writeRef = ref<HTMLElement | null>(null);
const previewRef = ref<HTMLElement | null>(null);

const titleRef = ref<HTMLTextAreaElement | null>(null);
const subRef = ref<HTMLTextAreaElement | null>(null);

function fit(ta: HTMLTextAreaElement | null) {
  if (!ta) return;
  ta.style.height = 'auto';
  ta.style.height = `${ta.scrollHeight}px`;
}
function resizeSource() {
  fit(titleRef.value);
  fit(subRef.value);
}
function autoGrow(e: Event) {
  fit(e.target as HTMLTextAreaElement);
}
/** 标题 / 副标题里按回车跳到下一栏，而不是换行 */
function focusNext(selector: string) {
  document.querySelector<HTMLElement>(selector)?.focus();
}

const isMac = ref(false);

function wrap(before: string, after = before, placeholder = '文字') {
  editorRef.value?.wrap(before, after, placeholder);
}
function prefixLines(prefix: (i: number) => string) {
  editorRef.value?.prefixLines(prefix);
}
function insertText(text: string) {
  editorRef.value?.insert(text);
}

const tools = [
  { icon: Heading2, label: '二级标题', run: () => prefixLines(() => '## ') },
  { icon: Bold, label: '粗体 (Ctrl+B)', run: () => wrap('**') },
  { icon: Italic, label: '斜体 (Ctrl+I)', run: () => wrap('*') },
  { icon: Code, label: '行内代码', run: () => wrap('`', '`', 'code') },
  { icon: Link2, label: '链接 (Ctrl+K)', run: () => wrap('[', '](https://)', '链接文字') },
  { icon: Quote, label: '引用', run: () => prefixLines(() => '> ') },
  { icon: List, label: '无序列表', run: () => prefixLines(() => '- ') },
  { icon: ListOrdered, label: '有序列表', run: () => prefixLines((i) => `${i + 1}. `) },
  { icon: SquareCode, label: '代码块', run: () => wrap('\n```ts\n', '\n```\n', '// code') },
];

/* ---------------- 同步滚动（分栏模式，按比例） ---------------- */
let syncing: 'write' | 'preview' | null = null;
function syncScroll(from: 'write' | 'preview') {
  if (view.value !== 'split' || (syncing && syncing !== from)) return;
  const a = from === 'write' ? writeRef.value : previewRef.value;
  const b = from === 'write' ? previewRef.value : writeRef.value;
  if (!a || !b) return;
  syncing = from;
  const ratio = a.scrollTop / Math.max(1, a.scrollHeight - a.clientHeight);
  b.scrollTop = ratio * (b.scrollHeight - b.clientHeight);
  window.setTimeout(() => { syncing = null; }, 60);
}

/* ---------------- 图片上传：按钮 / 拖入 / 粘贴，先插占位再替换 ---------------- */
const uploading = ref(0);
const dragOver = ref(false);
let dragDepth = 0;

async function uploadImage(file: File) {
  if (!file.type.startsWith('image/')) {
    toast.error('只支持图片文件', file.name);
    return;
  }
  const marker = `![上传中…](uploading-${Date.now().toString(36)})`;
  insertText(`\n${marker}\n`);
  uploading.value += 1;
  try {
    const sts = await adminFetch<any>('/api/v1/admin/media/sts', {
      method: 'POST',
      body: { filename: file.name, size_bytes: file.size, mime_type: file.type },
    });
    const form = new FormData();
    form.append('file', file);
    form.append('cos_key', sts.cos_key);
    const meta = await adminFetch<any>(sts.upload_url || '/api/v1/admin/media/upload-dev', { method: 'POST', body: form });
    await adminFetch('/api/v1/admin/media', {
      method: 'POST',
      body: {
        cos_key: sts.cos_key,
        url: meta.url,
        original_name: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        width: meta.width,
        height: meta.height,
        dominant_color: meta.dominant_color,
        lqip: meta.lqip,
        alt: file.name,
      },
    });
    const alt = file.name.replace(/\.[a-z0-9]+$/i, '');
    contentMd.value = contentMd.value.replace(marker, `![${alt}](${meta.url})`);
    toast.success('图片已插入', file.name);
  } catch (err) {
    contentMd.value = contentMd.value.replace(`\n${marker}\n`, '').replace(marker, '');
    toast.error('图片上传失败', apiErrorMessage(err));
  } finally {
    uploading.value -= 1;
  }
}

/* ---------------- 导入 Markdown 文件 ---------------- */
/** 读取 .md：识别 front matter 的 title / subtitle，或首行 `# 标题`，其余作为正文 */
async function onImportMd(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  let text = (await file.text()).replace(/^﻿/, '').replace(/\r\n/g, '\n');
  let importedTitle = '';
  let importedSub = '';
  const fm = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (fm) {
    importedTitle = fm[1].match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1] || '';
    importedSub = fm[1].match(/^(?:subtitle|description):\s*["']?(.+?)["']?\s*$/m)?.[1] || '';
    text = text.slice(fm[0].length);
  }
  const h1 = text.match(/^\s*#\s+(.+)\n+/);
  if (h1 && !importedTitle) {
    importedTitle = h1[1].trim();
    text = text.slice(h1[0].length);
  }
  if (contentMd.value.trim() && contentMd.value.trim() !== text.trim()) {
    const ok = await confirm({ title: '用导入的文件替换正文？', message: `「${file.name}」将替换当前正文，未保存的修改会丢失。`, confirmText: '替换' });
    if (!ok) return;
  }
  contentMd.value = text.replace(/^\n+/, '');
  if (importedTitle && (!title.value.trim() || isNew.value)) title.value = importedTitle;
  if (importedSub && !subtitle.value.trim()) subtitle.value = importedSub;
  nextTick(resizeSource);
  toast.success('已导入', file.name);
}

/* ---------------- 专注模式：隐藏后台侧栏，只留编辑器 ---------------- */
const focusMode = ref(false);
watch(focusMode, (on) => {
  document.documentElement.classList.toggle('a-focus', on);
  try { localStorage.setItem('blog_editor_focus', on ? '1' : '0'); } catch {}
});

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement;
  Array.from(input.files || []).forEach(uploadImage);
  input.value = '';
}
function onDragEnter(e: DragEvent) {
  if (!e.dataTransfer?.types.includes('Files')) return;
  dragDepth += 1;
  dragOver.value = true;
}
function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) dragOver.value = false;
}
function onDrop(e: DragEvent) {
  dragDepth = 0;
  dragOver.value = false;
  // 落在正文编辑器里的图片已由编辑器处理（会插到落点），这里只接住落在标题等其他位置的
  if (e.defaultPrevented) return;
  e.preventDefault();
  Array.from(e.dataTransfer?.files || []).forEach(uploadImage);
}

/* ---------------- 本地草稿（IndexedDB）与修订 ---------------- */
const drafts = useDraftStore();
const draftKey = computed(() => (isNew.value ? 'new' : postId.value));
const localSavedAt = ref('');
const recovery = ref<{ at: number; payload: DraftPayload } | null>(null);
const revisions = ref<Revision[]>([]);
let draftTimer: ReturnType<typeof setTimeout> | undefined;
let lastRevisionAt = Date.now();

function applyPayload(p: DraftPayload) {
  title.value = p.title;
  subtitle.value = p.subtitle;
  slug.value = p.slug || slug.value;
  contentMd.value = p.content_md;
  layoutVariant.value = p.layout_variant;
  accentColor.value = p.accent_color;
  tagIds.value = [...p.tag_ids];
  isFeatured.value = p.is_featured;
  isPinned.value = p.is_pinned;
  nextTick(resizeSource);
}

watch(() => JSON.stringify(payload()), () => {
  if (!loaded.value || !drafts.available) return;
  clearTimeout(draftTimer);
  draftTimer = setTimeout(async () => {
    // 每两分钟留一版修订；其余时候只覆盖当前草稿
    const kind = Date.now() - lastRevisionAt > 120_000 ? 'auto' : undefined;
    if (kind) lastRevisionAt = Date.now();
    const rec = await drafts.saveDraft(draftKey.value, payload() as DraftPayload, kind);
    if (rec) revisions.value = rec.revisions;
    localSavedAt.value = clock();
  }, 900);
});

async function checkRecovery(serverUpdatedAt?: string | null) {
  const local = await drafts.get(draftKey.value);
  revisions.value = local?.revisions || [];
  if (!local) return;
  const differs = JSON.stringify(local.payload) !== snapshot.value;
  const newer = !serverUpdatedAt || local.savedAt > new Date(serverUpdatedAt).getTime();
  const meaningful = local.payload.content_md.trim() || local.payload.title.trim();
  if (differs && newer && meaningful) recovery.value = { at: local.savedAt, payload: local.payload };
}
function restoreRecovery() {
  if (!recovery.value) return;
  applyPayload(recovery.value.payload);
  recovery.value = null;
  toast.success('已恢复本地草稿', '记得保存到服务器。');
}
async function restoreRevision(r: Revision) {
  const ok = await confirm({ title: '回到这一版？', message: `当前内容会先存成一版修订，再换成 ${fmtStamp(r.at)} 的版本（${r.words} 字）。`, confirmText: '回到这一版' });
  if (!ok) return;
  await drafts.saveDraft(draftKey.value, payload() as DraftPayload, 'restore');
  applyPayload(r.payload);
  revisions.value = await drafts.revisions(draftKey.value);
  toast.success('已回到所选版本', fmtStamp(r.at));
}
function fmtStamp(t: number) {
  const d = new Date(t);
  const today = new Date().toDateString() === d.toDateString();
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return today ? `今天 ${hm}` : `${d.getMonth() + 1} 月 ${d.getDate()} 日 ${hm}`;
}
const REV_KIND: Record<Revision['kind'], string> = { auto: '自动', save: '保存', restore: '恢复前' };

/* ---------------- 读取 / 保存 ---------------- */
async function load() {
  adminFetch<any[]>('/api/v1/tags').then((t) => { availableTags.value = t || []; }).catch(() => {});
  let serverUpdatedAt: string | null = null;
  if (isNew.value) {
    contentMd.value = '## 新章节\n\n在此开始撰写特稿正文……\n\n> [!NOTE]\n> 支持 GitHub Alerts、代码高亮、终端块与图片直传。\n';
  } else {
    try {
      const d = await adminFetch<any>(`/api/v1/admin/posts/${postId.value}`);
      title.value = d.title || '';
      subtitle.value = d.subtitle || '';
      slug.value = d.slug || '';
      contentMd.value = d.content_md || '';
      layoutVariant.value = d.layout_variant || 'standard';
      accentColor.value = d.accent_color || PIGMENT_SWATCHES[0].hex;
      serverUpdatedAt = d.updated_at || d.content_updated_at || null;
      status.value = d.status === 'published' ? 'published' : 'draft';
      tagIds.value = (d.tags || []).map((t: any) => t.id);
      isFeatured.value = !!d.is_featured;
      isPinned.value = !!d.is_pinned;
      number.value = d.number ?? null;
    } catch (err) {
      toast.error('特稿加载失败', apiErrorMessage(err));
    }
  }
  await renderPreview();
  markClean();
  loaded.value = true;
  nextTick(resizeSource);
  checkRecovery(serverUpdatedAt);
}

async function save(nextStatus?: 'draft' | 'published') {
  if (saving.value) return;
  if (!title.value.trim()) {
    toast.error('还缺一个标题', '标题会成为文章的门面，也决定默认的链接。');
    nextTick(() => document.querySelector<HTMLInputElement>('.ed-title')?.focus());
    return;
  }
  saving.value = nextStatus === 'published' && status.value !== 'published' ? 'publish' : 'save';
  const body: Record<string, unknown> = { ...payload(), status: nextStatus || status.value };
  try {
    if (isNew.value) {
      const d = await adminFetch<any>('/api/v1/admin/posts', { method: 'POST', body });
      status.value = (body.status as 'draft' | 'published');
      slug.value = d.slug || slug.value;
      number.value = d.number ?? number.value;
      markClean();
      lastSavedAt.value = clock();
      justCreated = true;
      await drafts.saveDraft('new', payload() as DraftPayload, 'save');
      await drafts.move('new', String(d.id));
      await router.replace(`/admin/posts/${d.id}`);
    } else {
      const d = await adminFetch<any>(`/api/v1/admin/posts/${postId.value}`, { method: 'PATCH', body });
      status.value = d.status === 'published' ? 'published' : 'draft';
      slug.value = d.slug || slug.value;
      markClean();
      lastSavedAt.value = clock();
      const rec = await drafts.saveDraft(draftKey.value, payload() as DraftPayload, 'save');
      if (rec) revisions.value = rec.revisions;
    }
    recovery.value = null;
    if (saving.value === 'publish') toast.success('已发布', '文章已在前台上线。');
    else toast.success(status.value === 'published' ? '更新已上线' : '草稿已保存');
  } catch (err) {
    toast.error('保存失败', apiErrorMessage(err));
  } finally {
    saving.value = '';
  }
}

/** 编辑器实例被复用：仅在切换到另一篇文章时重新读取（新建后的地址替换除外） */
let justCreated = false;
watch(postId, () => {
  if (justCreated) {
    justCreated = false;
    return;
  }
  loaded.value = false;
  lastSavedAt.value = '';
  recovery.value = null;
  load();
});

function clock() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/* ---------------- 设置面板 ---------------- */
const LAYOUTS = [
  { value: 'standard', label: '特稿', hint: '标题跨十栏 · 水墨长卷' },
  { value: 'wide', label: '图解', hint: '代码与图破栏到 1080' },
  { value: 'immersive', label: '沉浸', hint: '整屏头图 · 揭版' },
  { value: 'essay', label: '随笔', hint: '首字下沉 · 无头图' },
  { value: 'showcase', label: '陈列', hint: '横向章节扉页' },
];
const pigmentName = computed(() => pigmentFor(accentColor.value).name);
function toggleTag(id: number) {
  tagIds.value = tagIds.value.includes(id) ? tagIds.value.filter((t) => t !== id) : [...tagIds.value, id];
}

/* ---------------- 快捷键与离开保护 ---------------- */
function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    save();
  }
}
function onBeforeUnload(e: BeforeUnloadEvent) {
  if (dirty.value) {
    e.preventDefault();
    e.returnValue = '';
  }
}
onBeforeRouteLeave(async () => {
  if (!dirty.value) return true;
  return await confirm({ title: '放弃未保存的更改？', message: '离开后，本次编辑尚未保存的内容将会丢失。', confirmText: '放弃并离开', danger: true });
});

onMounted(() => {
  isMac.value = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  try {
    const v = localStorage.getItem('blog_editor_view');
    if (v === 'write' || v === 'split' || v === 'preview') view.value = v;
    focusMode.value = localStorage.getItem('blog_editor_focus') === '1';
  } catch {}
  window.addEventListener('keydown', onKeydown);
  window.addEventListener('beforeunload', onBeforeUnload);
  window.addEventListener('resize', resizeSource);
  load();
});
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  window.removeEventListener('beforeunload', onBeforeUnload);
  window.removeEventListener('resize', resizeSource);
  clearTimeout(previewTimer);
  document.documentElement.classList.remove('a-focus');
});
</script>

<template>
  <div class="ed" :style="{ '--ed-accent': accentColor }">
    <!-- 顶栏 -->
    <header class="ed-bar">
      <div class="ed-bar-left">
        <NuxtLink to="/admin/posts" class="a-icon-btn" aria-label="返回特稿列表" title="返回特稿列表"><ArrowLeft :size="17" /></NuxtLink>
        <span class="ed-crumb">
          <span class="a-faint">特稿</span>
          <span class="a-faint">/</span>
          <span class="a-mono">{{ isNew ? '新建' : `No.${issueNo(number)}` }}</span>
        </span>
        <span class="a-status" :class="status === 'published' ? 'is-ok' : 'is-warn'">{{ status === 'published' ? '已发布' : '草稿' }}</span>
        <span class="ed-save" :class="{ 'is-dirty': dirty, 'is-busy': !!saving }">
          <i aria-hidden="true" />{{ saveLabel }}
        </span>
        <span v-if="localSavedAt && dirty" class="ed-local" title="未保存的改动已在本机留存，关掉页面也不会丢">本机已存 {{ localSavedAt }}</span>
      </div>

      <UiSegmented v-model="view" :options="viewOptions" size="sm" aria-label="视图模式" class="ed-views" />

      <div class="ed-bar-right">
        <button type="button" class="a-btn a-btn-sm" :class="{ 'is-on': settingsOpen }" @click="settingsOpen = true">
          <SlidersHorizontal :size="14" :stroke-width="1.5" /> 设置
          <span v-if="revisions.length" class="ed-rev-count" :title="`本机有 ${revisions.length} 版修订`"><History :size="11" :stroke-width="1.75" />{{ revisions.length }}</span>
        </button>
        <button type="button" class="a-btn a-btn-sm" :disabled="!!saving" title="保存（Ctrl+S）" @click="save()">
          <span v-if="saving === 'save'" class="a-spin" /><Save v-else :size="14" :stroke-width="2" />
          保存
          <kbd class="a-kbd ed-kbd">{{ isMac ? '⌘S' : 'Ctrl S' }}</kbd>
        </button>
        <button v-if="status !== 'published'" type="button" class="a-btn a-btn-sm a-btn-accent" :disabled="!!saving" @click="save('published')">
          <span v-if="saving === 'publish'" class="a-spin" /><Send v-else :size="14" :stroke-width="2" />
          发布
        </button>
        <a v-else-if="slug" :href="`/posts/${slug}`" target="_blank" rel="noopener" class="a-btn a-btn-sm a-btn-primary">查看线上 ↗</a>
      </div>
    </header>

    <!-- 工具条 -->
    <div v-show="view !== 'preview'" class="ed-tools">
      <button v-for="t in tools" :key="t.label" type="button" class="a-icon-btn" :title="t.label" :aria-label="t.label" @mousedown.prevent @click="t.run">
        <component :is="t.icon" :size="16" :stroke-width="1.75" />
      </button>
      <span class="ed-tools-sep" />
      <label class="a-icon-btn ed-upload" :title="uploading ? '上传中…' : '插入图片（也可拖入或粘贴）'">
        <span v-if="uploading" class="a-spin" />
        <ImagePlus v-else :size="16" :stroke-width="1.75" />
        <input type="file" accept="image/*" multiple class="sr-only" @change="onFileInput">
      </label>
      <label class="a-icon-btn ed-upload" title="导入 Markdown 文件">
        <FileUp :size="16" :stroke-width="1.75" />
        <input type="file" accept=".md,.markdown,.txt,text/markdown,text/plain" class="sr-only" @change="onImportMd">
      </label>
      <span class="ed-tools-hint a-faint">拖入或粘贴图片即可上传</span>
      <button type="button" class="a-icon-btn ed-focus" :class="{ 'is-on': focusMode }" :title="focusMode ? '退出专注模式' : '专注模式（隐藏侧栏）'" :aria-pressed="focusMode" @click="focusMode = !focusMode">
        <Minimize2 v-if="focusMode" :size="16" :stroke-width="1.75" />
        <Maximize2 v-else :size="16" :stroke-width="1.75" />
      </button>
    </div>

    <!-- 本地草稿比服务器上的新：给出恢复的机会 -->
    <Transition name="ed-recover">
      <div v-if="recovery" class="ed-recover" role="status">
        <span class="ed-recover-seal" aria-hidden="true">稿</span>
        <span>本机有一份 {{ fmtStamp(recovery.at) }} 的草稿，比服务器上的版本新（{{ recovery.payload.content_md.length.toLocaleString() }} 字符）。</span>
        <button type="button" class="a-btn a-btn-sm a-btn-primary" @click="restoreRecovery">恢复本地草稿</button>
        <button type="button" class="a-btn a-btn-sm a-btn-quiet" @click="recovery = null">忽略</button>
      </div>
    </Transition>

    <!-- 工作区 -->
    <div class="ed-body" :class="`is-${view}`">
      <div
        class="ed-col ed-col-write"
        @dragenter.prevent="onDragEnter"
        @dragover.prevent
        @dragleave="onDragLeave"
        @drop="onDrop"
      >
      <section ref="writeRef" class="ed-pane ed-write" data-lenis-prevent @scroll.passive="syncScroll('write')">
        <div class="ed-write-inner">
          <textarea
            ref="titleRef"
            v-model="title"
            class="ed-title"
            rows="1"
            placeholder="标题"
            aria-label="标题"
            maxlength="120"
            @input="autoGrow"
            @keydown.enter.prevent="focusNext('.ed-sub')"
          />
          <textarea
            ref="subRef"
            v-model="subtitle"
            class="ed-sub"
            rows="1"
            placeholder="副标题：一句话点明这篇文章的价值（可选）"
            aria-label="副标题"
            maxlength="200"
            @input="autoGrow"
            @keydown.enter.prevent="focusNext('.ed-src')"
          />
          <span class="ed-rule" aria-hidden="true" />
          <AdminMarkdownEditor
            ref="editorRef"
            v-model="contentMd"
            placeholder="用 Markdown 写下正文……"
            @caret="caret = $event"
            @paste-files="(files) => files.forEach(uploadImage)"
          />
        </div>
      </section>
      <Transition name="ed-drop">
        <div v-if="dragOver" class="ed-drop" aria-hidden="true">
          <span class="ed-drop-ring"><Upload :size="22" :stroke-width="1.75" /></span>
          <p>松手即上传，图片会插入到光标处</p>
        </div>
      </Transition>
      </div>

      <section ref="previewRef" class="ed-pane ed-preview" data-lenis-prevent @scroll.passive="syncScroll('preview')">
        <AdminMdPreview
          :html="previewHtml"
          :markdown="contentMd"
          :title="title"
          :subtitle="subtitle"
          :number="number"
          :accent="accentColor"
          :layout-variant="layoutVariant"
          :word-count="wordCount"
          :reading-minutes="readingMinutes"
        />
      </section>
    </div>

    <!-- 状态栏 -->
    <footer class="ed-status">
      <span>{{ wordCount.toLocaleString() }} 字</span>
      <span>约 {{ readingMinutes }} 分钟</span>
      <span>行 {{ caret.line }} · 列 {{ caret.col }}</span>
      <span v-if="previewing" class="ed-status-busy"><span class="a-spin" /> 排版中</span>
      <span class="ed-status-right">Markdown · {{ LAYOUTS.find((l) => l.value === layoutVariant)?.label }}模板 · 设色 {{ pigmentName }}</span>
    </footer>

    <!-- 设置面板 -->
    <AdminDrawer :open="settingsOpen" title="文章设置" subtitle="链接、版式、设色、归类与修订" @close="settingsOpen = false">
      <div class="a-field">
        <label class="a-label" for="ed-slug">链接 <small>/posts/…</small></label>
        <input id="ed-slug" v-model="slug" class="a-input is-mono" type="text" placeholder="留空则按标题自动生成">
      </div>

      <div class="a-field">
        <span class="a-label">版式模板</span>
        <div class="layouts">
          <button
            v-for="l in LAYOUTS"
            :key="l.value"
            type="button"
            class="layout-card"
            :class="[`is-${l.value}`, { 'is-on': layoutVariant === l.value }]"
            :aria-pressed="layoutVariant === l.value"
            @click="layoutVariant = l.value"
          >
            <span class="layout-art" aria-hidden="true"><InkCover :seed="slug || title || 'draft'" :variant="variantForLayout(l.value)" :accent="accentColor" :width="200" :height="120" :numeral="false" :seal="false" /></span>
            <span class="layout-name">{{ l.label }}</span>
            <span class="layout-hint">{{ l.hint }}</span>
          </button>
        </div>
      </div>

      <div class="a-field">
        <span class="a-label">设色 <small>{{ pigmentName }} · {{ accentColor }}</small></span>
        <div class="swatches">
          <button
            v-for="c in PIGMENT_SWATCHES"
            :key="c.hex"
            type="button"
            class="swatch"
            :class="{ 'is-on': accentColor.toLowerCase() === c.hex.toLowerCase() }"
            :style="{ '--c': c.hex }"
            :aria-label="`设色：${c.name}`"
            :title="c.name"
            @click="accentColor = c.hex"
          ><span class="swatch-name">{{ c.name }}</span></button>
        </div>
        <p class="a-hint">前台会把强调色就近归到这八种传统颜料，保证和水墨、朱砂的气质一致，且小字号对纸色的对比度不低于 4.5:1。</p>
      </div>

      <div class="a-field">
        <span class="a-label">标签 <small>已选 {{ tagIds.length }}</small></span>
        <div class="tag-set">
          <button
            v-for="t in availableTags"
            :key="t.id"
            type="button"
            class="a-chip"
            :class="{ 'is-on': tagIds.includes(t.id) }"
            @click="toggleTag(t.id)"
          ><i :style="{ color: t.color || 'var(--color-ink-faint)' }" />{{ t.name }}</button>
        </div>
      </div>

      <div class="flags">
        <div class="flag">
          <div>
            <p class="flag-title">精选</p>
            <p class="a-hint">在首页画布中优先展示</p>
          </div>
          <AdminSwitch v-model="isFeatured" label="精选" />
        </div>
        <div class="flag">
          <div>
            <p class="flag-title">置顶</p>
            <p class="a-hint">固定在文章索引最前</p>
          </div>
          <AdminSwitch v-model="isPinned" label="置顶" />
        </div>
      </div>

      <div class="a-field">
        <span class="a-label">修订版本 <small>本机 · 最多 30 版</small></span>
        <ol v-if="revisions.length" class="revs">
          <li v-for="r in revisions" :key="r.at" class="rev">
            <span class="rev-kind" :class="`is-${r.kind}`">{{ REV_KIND[r.kind] }}</span>
            <span class="rev-time">{{ fmtStamp(r.at) }}</span>
            <span class="rev-words a-mono">{{ r.words.toLocaleString() }} 字</span>
            <button type="button" class="a-btn a-btn-sm a-btn-quiet" @click="restoreRevision(r)">回到这一版</button>
          </li>
        </ol>
        <p v-else class="a-hint">还没有修订。写作时每两分钟、每次保存都会在本机留一版。</p>
      </div>

      <template #footer>
        <span class="a-hint drawer-note">设置随文章一起保存</span>
        <button type="button" class="a-btn" @click="settingsOpen = false">完成</button>
        <button type="button" class="a-btn a-btn-primary" :disabled="!!saving" @click="save(); settingsOpen = false">保存</button>
      </template>
    </AdminDrawer>
  </div>
</template>

<style scoped>
.ed {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  background: var(--a-paper);
}

/* ---------------- 顶栏 ---------------- */
.ed-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 16px;
  height: 56px;
  padding: 0 16px;
  background: var(--a-desk);
  border-bottom: 1px solid var(--color-ink);
}
.ed-bar-left, .ed-bar-right { display: flex; align-items: center; gap: 10px; min-width: 0; }
.ed-bar-right { justify-content: flex-end; gap: 8px; }
.ed-crumb { display: inline-flex; gap: 6px; font-size: 13px; white-space: nowrap; }
.ed-save {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--color-ink-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ed-save i { width: 6px; height: 6px; border-radius: 1px; background: var(--a-ok); transition: background-color var(--a-dur) ease; }
.ed-local { font-family: var(--font-mono); font-size: 10.5px; color: var(--color-ink-faint); white-space: nowrap; }
.ed-rev-count { display: inline-flex; align-items: center; gap: 3px; margin-left: 2px; padding: 0 5px; height: 16px; font-family: var(--font-mono); font-size: 10px; color: var(--color-ink-muted); border: 1px solid var(--color-line); border-radius: 2px; }
.ed-save.is-dirty { color: var(--color-ink-muted); }
.ed-save.is-dirty i { background: var(--a-warn); animation: dirty-pulse 1.8s ease-in-out infinite; }
.ed-save.is-busy i { background: var(--color-ink); }
@keyframes dirty-pulse { 50% { box-shadow: 0 0 0 4px color-mix(in oklab, var(--a-warn) 18%, transparent); } }
.ed-kbd { margin-left: 2px; }
.a-btn.is-on { background: var(--a-press); }

/* ---------------- 工具条 ---------------- */
.ed-tools {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 44px;
  padding: 0 14px;
  border-bottom: 1px solid var(--color-line);
  background: var(--a-paper);
}
.ed-tools-sep { width: 1px; height: 18px; margin: 0 8px; background: var(--color-line); }
.ed-upload { cursor: pointer; }
.ed-focus { margin-left: auto; }
.ed-tools-hint { margin-left: 10px; font-size: 12px; }

/* ---------------- 工作区 ---------------- */
.ed-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: minmax(0, 1fr); }
.ed-body.is-write,
.ed-body.is-preview { grid-template-columns: 1fr; }
.ed-col { position: relative; display: flex; min-width: 0; min-height: 0; }
.ed-col > .ed-pane { flex: 1; }
.ed-pane { position: relative; min-width: 0; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
.ed-body.is-write .ed-preview,
.ed-body.is-preview .ed-col-write { display: none; }
.ed-col-write { border-right: 1px solid var(--color-line); }
.ed-body.is-write .ed-col-write { border-right: 0; }

.ed-write-inner {
  max-width: 760px;
  margin: 0 auto;
  padding: 44px clamp(24px, 4vw, 56px) 120px;
}
.ed-title,
.ed-sub {
  display: block;
  width: 100%;
  padding: 0;
  overflow: hidden;
  resize: none;
  border: 0;
  background: transparent;
  color: var(--color-ink);
}
.ed-title {
  font-family: var(--font-serif);
  font-size: clamp(26px, 2.6vw, 36px);
  font-weight: 900;
  line-height: 1.3;
  letter-spacing: -0.02em;
}
.ed-sub {
  margin-top: 10px;
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.7;
  color: var(--color-ink-muted);
}
.ed-title::placeholder, .ed-sub::placeholder { color: var(--color-ink-faint); }
.ed-title:focus, .ed-sub:focus { outline: none; }
.ed-rule {
  display: block;
  width: 48px;
  height: 2px;
  margin: 22px 0 26px;
  background: var(--ed-accent);
  transition: width var(--a-dur-lg) var(--ease-out-expo), background-color var(--a-dur) ease;
}
.ed-write:focus-within .ed-rule { width: 96px; }
/* 本地草稿提示 */
.ed-recover {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 14px;
  padding: 10px 16px;
  font-size: 13px;
  background: color-mix(in oklab, var(--a-warn) 9%, var(--a-paper));
  border-bottom: 1px solid var(--color-line);
}
.ed-recover-seal { display: grid; place-items: center; width: 22px; height: 22px; font-family: var(--font-serif); font-size: 12px; font-weight: 900; color: var(--day-bg); background: var(--color-ink); border-radius: 2px; transform: rotate(-4deg); }
.ed-recover-enter-active { transition: opacity var(--a-dur-md) ease, transform var(--a-dur-md) var(--ease-out-expo); }
.ed-recover-leave-active { transition: opacity var(--a-dur) ease; }
.ed-recover-enter-from { opacity: 0; transform: translateY(-6px); }
.ed-recover-leave-to { opacity: 0; }

/* 拖入图片时的蒙层 */
.ed-drop {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  font-size: 13.5px;
  color: var(--color-ink);
  background: color-mix(in oklab, var(--color-bg) 82%, transparent);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
  outline: 1px dashed var(--color-ink);
  outline-offset: -14px;
  pointer-events: none;
}
.ed-drop-ring {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  color: var(--color-ink);
  background: color-mix(in oklab, var(--color-ink) 8%, transparent);
  -webkit-mask-image: var(--ink-blot);
  mask-image: var(--ink-blot);
  -webkit-mask-size: 150% 150%;
  mask-size: 150% 150%;
  -webkit-mask-position: 50% 50%;
  mask-position: 50% 50%;
}
.ed-drop-enter-active, .ed-drop-leave-active { transition: opacity var(--a-dur) ease; }
.ed-drop-enter-from, .ed-drop-leave-to { opacity: 0; }

/* 预览：排版主题纸面由 AdminMdPreview 渲染 */
.ed-preview { background: var(--a-desk); }

/* ---------------- 状态栏 ---------------- */
.ed-status {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 32px;
  padding: 0 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-faint);
  background: var(--a-desk);
  border-top: 1px solid var(--color-line);
  font-variant-numeric: tabular-nums;
}
.ed-status-busy { display: inline-flex; align-items: center; gap: 6px; }
.ed-status-right { margin-left: auto; }

/* ---------------- 设置面板 ---------------- */
.layouts { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 8px; }
.layout-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 8px 10px;
  text-align: left;
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius-sm);
  transition: border-color var(--a-dur) ease, background-color var(--a-dur) ease, transform var(--dur-impress) var(--ease-impress);
}
.layout-card:hover { border-color: var(--color-line-strong); }
.layout-card:active { transform: scale(0.97); }
.layout-card.is-on { border-color: var(--color-ink); box-shadow: inset 0 0 0 1px var(--color-ink); }
/* 版式缩略：每种模板对应的头图构图（与前台一致） */
.layout-art {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 5 / 3;
  margin-bottom: 6px;
  overflow: hidden;
  border: 1px solid var(--color-line);
}
.is-essay .layout-art { opacity: 0.35; }
.layout-name { font-size: 12.5px; font-weight: 600; }
.layout-hint { font-size: 10.5px; color: var(--color-ink-faint); }

/* 设色：八种传统颜料，每一块是一枚小色印，名字写在印下 */
.swatches { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 6px; }
.swatch {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 6px 0 4px;
  border-radius: var(--a-radius-sm);
  transition: background-color var(--a-dur) ease, transform var(--dur-impress) var(--ease-impress);
}
.swatch::before {
  content: "";
  width: 26px;
  height: 26px;
  border-radius: 2px;
  background: var(--c);
  transform: rotate(-3deg);
  transition: transform var(--a-dur-md) var(--ease-out-back);
}
.swatch:hover { background: var(--a-hover); }
.swatch:hover::before { transform: rotate(3deg) scale(1.06); }
.swatch:active { transform: scale(0.95); }
.swatch.is-on { background: var(--a-press); box-shadow: inset 0 -2px 0 var(--color-ink); }
.swatch-name { font-family: var(--font-serif); font-size: 11px; font-weight: 700; color: var(--color-ink-muted); }
.swatch.is-on .swatch-name { color: var(--color-ink); }

/* 修订版本 */
.revs { list-style: none; border-top: 1px solid var(--color-line); max-height: 240px; overflow-y: auto; }
.rev { display: grid; grid-template-columns: 48px minmax(0, 1fr) auto auto; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--color-line); font-size: 12.5px; }
.rev-kind { font-family: var(--font-serif); font-size: 11px; font-weight: 700; color: var(--color-ink-faint); }
.rev-kind.is-save { color: var(--a-ok); }
.rev-kind.is-restore { color: var(--a-warn); }
.rev-words { font-size: 11px; color: var(--color-ink-faint); }

.tag-set { display: flex; flex-wrap: wrap; gap: 6px; }
.flags { display: flex; flex-direction: column; border: 1px solid var(--color-line); border-radius: var(--a-radius); }
.flag { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; }
.flag + .flag { border-top: 1px solid var(--color-line); }
.flag-title { font-size: 13.5px; font-weight: 600; }
.drawer-note { margin-right: auto; }

@media (max-width: 1100px) {
  .ed-tools-hint, .ed-kbd { display: none; }
}
@media (max-width: 860px) {
  .ed-bar { grid-template-columns: minmax(0, 1fr) auto; height: auto; padding-block: 10px; row-gap: 10px; }
  .ed-views { grid-column: 1 / -1; grid-row: 2; justify-self: start; }
  .ed-save, .ed-crumb { display: none; }
  .ed-body.is-split { grid-template-columns: 1fr; }
  .ed-body.is-split .ed-preview { display: none; }
  .layouts { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .swatches { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
</style>
