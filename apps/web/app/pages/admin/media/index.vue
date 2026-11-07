<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { Upload, Search, Copy, Link2, Maximize2, Trash2, ImageOff, X, Check } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';

definePageMeta({ layout: 'admin' });
useHead({ title: '媒体库 · 编辑部后台' });

const toast = useToast();
const { confirm } = useConfirm();

const items = ref<any[]>([]);
const total = ref(0);
const loading = ref(true);
const query = ref('');
const loadedIds = ref(new Set<number>());
const copied = ref('');

/** 上传队列：每个文件一行，完成后淡出 */
const queue = ref<Array<{ id: string; name: string; state: 'up' | 'ok' | 'err' }>>([]);
const dragging = ref(false);
let dragDepth = 0;

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return q ? items.value.filter((m) => `${m.original_name} ${m.alt || ''}`.toLowerCase().includes(q)) : items.value;
});
const totalSize = computed(() => items.value.reduce((s, m) => s + (m.size_bytes || 0), 0));

async function load() {
  loading.value = true;
  try {
    const d = await adminFetch<any>('/api/v1/admin/media', { query: { page_size: 100 } });
    items.value = d.items || [];
    total.value = d.total || 0;
  } catch (err) {
    toast.error('媒体库加载失败', apiErrorMessage(err));
  } finally {
    loading.value = false;
  }
}

async function uploadOne(file: File) {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  queue.value.push({ id, name: file.name, state: 'up' });
  const mark = (state: 'ok' | 'err') => {
    const job = queue.value.find((j) => j.id === id);
    if (job) job.state = state;
    setTimeout(() => { queue.value = queue.value.filter((j) => j.id !== id); }, state === 'ok' ? 1400 : 4000);
  };
  if (!file.type.startsWith('image/')) {
    mark('err');
    toast.error('只支持图片文件', file.name);
    return;
  }
  try {
    const sts = await adminFetch<any>('/api/v1/admin/media/sts', {
      method: 'POST',
      body: { filename: file.name, size_bytes: file.size, mime_type: file.type },
    });
    const form = new FormData();
    form.append('file', file);
    form.append('cos_key', sts.cos_key);
    const meta = await adminFetch<any>(sts.upload_url || '/api/v1/admin/media/upload-dev', { method: 'POST', body: form });
    const created = await adminFetch<any>('/api/v1/admin/media', {
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
    items.value.unshift(created?.id ? created : { ...meta, id: Date.now(), original_name: file.name, size_bytes: file.size });
    total.value += 1;
    mark('ok');
  } catch (err) {
    mark('err');
    toast.error('上传失败', `${file.name} · ${apiErrorMessage(err)}`);
  }
}

function uploadFiles(files: FileList | File[] | null | undefined) {
  Array.from(files || []).forEach(uploadOne);
}
function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement;
  uploadFiles(input.files);
  input.value = '';
}

/* 整页拖放 */
function onDragEnter(e: DragEvent) {
  if (!e.dataTransfer?.types.includes('Files')) return;
  dragDepth += 1;
  dragging.value = true;
}
function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) dragging.value = false;
}
function onDrop(e: DragEvent) {
  e.preventDefault();
  dragDepth = 0;
  dragging.value = false;
  uploadFiles(e.dataTransfer?.files);
}
const prevent = (e: DragEvent) => e.preventDefault();

async function copy(kind: 'md' | 'url', m: any) {
  const text = kind === 'md' ? `![${m.alt || m.original_name}](${m.url})` : new URL(m.url, location.origin).href;
  try {
    await navigator.clipboard.writeText(text);
    copied.value = `${kind}-${m.id}`;
    setTimeout(() => { if (copied.value === `${kind}-${m.id}`) copied.value = ''; }, 1500);
    toast.success(kind === 'md' ? '已复制 Markdown' : '已复制链接', m.original_name);
  } catch {
    toast.error('复制失败', '浏览器拒绝了剪贴板访问');
  }
}

async function remove(m: any) {
  const ok = await confirm({ title: '删除这张图片？', message: `「${m.original_name}」将移入回收站。已经引用它的文章会显示为破图。`, confirmText: '删除', danger: true });
  if (!ok) return;
  try {
    await adminFetch(`/api/v1/admin/media/${m.id}`, { method: 'DELETE' });
    items.value = items.value.filter((x) => x.id !== m.id);
    total.value -= 1;
    if (preview.value?.id === m.id) preview.value = null;
    toast.success('已删除', m.original_name);
  } catch (err) {
    toast.error('删除失败', apiErrorMessage(err));
  }
}

/* 灯箱 */
const preview = ref<any | null>(null);
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') preview.value = null;
}

onMounted(() => {
  load();
  window.addEventListener('dragenter', onDragEnter);
  window.addEventListener('dragleave', onDragLeave);
  window.addEventListener('dragover', prevent);
  window.addEventListener('drop', onDrop);
  window.addEventListener('keydown', onKey);
});
onBeforeUnmount(() => {
  window.removeEventListener('dragenter', onDragEnter);
  window.removeEventListener('dragleave', onDragLeave);
  window.removeEventListener('dragover', prevent);
  window.removeEventListener('drop', onDrop);
  window.removeEventListener('keydown', onKey);
});
</script>

<template>
  <div>
    <AdminPageHeader index="03" en="Media" title="媒体库">
      <template #description>{{ total }} 项资产 · 共 {{ fileSize(totalSize) }} · 拖入页面任意位置即可上传</template>
      <label class="a-btn a-btn-primary upload-btn">
        <Upload :size="14" :stroke-width="2" /> 上传图片
        <input type="file" accept="image/*" multiple class="sr-only" @change="onFileInput">
      </label>
    </AdminPageHeader>

    <div class="toolbar a-rise" style="--i: 1">
      <label class="a-input-icon search">
        <Search :size="15" :stroke-width="2" />
        <input v-model="query" type="search" class="a-input" placeholder="按文件名筛选…" aria-label="按文件名筛选">
      </label>
      <span class="a-faint toolbar-note">{{ filtered.length }} / {{ items.length }}</span>
    </div>

    <div v-if="loading" class="grid">
      <div v-for="i in 12" :key="i" class="tile is-skel"><span class="a-skel tile-skel" /></div>
    </div>

    <TransitionGroup v-else-if="filtered.length" tag="div" name="a-list" class="grid">
      <figure v-for="m in filtered" :key="m.id" class="tile">
        <div class="tile-img" :style="{ '--mat': m.dominant_color || 'var(--color-ink)', backgroundImage: m.lqip ? `url(${m.lqip})` : undefined }">
          <img
            :src="m.url"
            :alt="m.alt || m.original_name"
            loading="lazy"
            :class="{ 'is-loaded': loadedIds.has(m.id) }"
            @load="loadedIds.add(m.id)"
            @error="loadedIds.add(m.id)"
          >
          <div class="tile-actions">
            <button type="button" class="tile-btn" title="复制 Markdown" aria-label="复制 Markdown" @click="copy('md', m)">
              <Check v-if="copied === `md-${m.id}`" :size="15" /><Copy v-else :size="15" :stroke-width="1.75" />
            </button>
            <button type="button" class="tile-btn" title="复制链接" aria-label="复制链接" @click="copy('url', m)">
              <Check v-if="copied === `url-${m.id}`" :size="15" /><Link2 v-else :size="15" :stroke-width="1.75" />
            </button>
            <button type="button" class="tile-btn" title="预览" aria-label="预览" @click="preview = m"><Maximize2 :size="15" :stroke-width="1.75" /></button>
            <button type="button" class="tile-btn is-danger" title="删除" aria-label="删除" @click="remove(m)"><Trash2 :size="15" :stroke-width="1.75" /></button>
          </div>
        </div>
        <figcaption class="tile-meta">
          <span class="tile-name" :title="m.original_name">{{ m.original_name }}</span>
          <span class="tile-sub a-mono">
            <i :style="{ background: m.dominant_color || 'var(--color-line-strong)' }" />
            {{ m.width && m.height ? `${m.width}×${m.height}` : '—' }} · {{ fileSize(m.size_bytes) }}
          </span>
        </figcaption>
      </figure>
    </TransitionGroup>

    <div v-else class="a-card">
      <AdminEmpty :title="query ? '没有匹配的文件' : '媒体库还是空的'" :hint="query ? '换个文件名关键词试试。' : '把图片拖到页面上，或点击右上角上传。会自动转为 WebP 并提取主色。'">
        <template #icon><ImageOff :size="20" :stroke-width="1.6" /></template>
      </AdminEmpty>
    </div>

    <!-- 上传队列 -->
    <Teleport to="body">
      <TransitionGroup tag="div" name="a-list" class="queue">
        <div v-for="j in queue" :key="j.id" class="queue-item" :class="`is-${j.state}`">
          <span v-if="j.state === 'up'" class="a-spin" />
          <Check v-else-if="j.state === 'ok'" :size="14" />
          <X v-else :size="14" />
          <span class="queue-name">{{ j.name }}</span>
          <span class="queue-bar"><i /></span>
        </div>
      </TransitionGroup>
    </Teleport>

    <!-- 整页拖放蒙层 -->
    <Teleport to="body">
      <Transition name="drop">
        <div v-if="dragging" class="dropzone" aria-hidden="true">
          <div class="dropzone-card">
            <span class="dropzone-ring"><Upload :size="26" :stroke-width="1.6" /></span>
            <p class="dropzone-title">松手上传到媒体库</p>
            <p class="dropzone-hint">支持一次拖入多张图片</p>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- 灯箱 -->
    <Teleport to="body">
      <Transition name="lb">
        <div v-if="preview" class="lb" role="dialog" aria-modal="true" :aria-label="preview.original_name" @mousedown.self="preview = null">
          <div class="lb-stage" @mousedown.self="preview = null">
            <img :src="preview.url" :alt="preview.alt || preview.original_name">
          </div>
          <aside class="lb-info">
            <button type="button" class="a-icon-btn lb-close" aria-label="关闭预览" @click="preview = null"><X :size="17" /></button>
            <p class="lb-name">{{ preview.original_name }}</p>
            <dl class="lb-dl">
              <div><dt>尺寸</dt><dd class="a-mono">{{ preview.width }} × {{ preview.height }}</dd></div>
              <div><dt>大小</dt><dd class="a-mono">{{ fileSize(preview.size_bytes) }}</dd></div>
              <div><dt>类型</dt><dd class="a-mono">{{ preview.mime_type }}</dd></div>
              <div><dt>主色</dt><dd class="a-mono"><i class="lb-swatch" :style="{ background: preview.dominant_color }" />{{ preview.dominant_color || '—' }}</dd></div>
              <div><dt>上传</dt><dd>{{ timeAgo(preview.created_at) }}</dd></div>
            </dl>
            <code class="lb-url">{{ preview.url }}</code>
            <div class="lb-actions">
              <button type="button" class="a-btn a-btn-sm" @click="copy('md', preview)"><Copy :size="13" /> Markdown</button>
              <button type="button" class="a-btn a-btn-sm" @click="copy('url', preview)"><Link2 :size="13" /> 链接</button>
              <button type="button" class="a-btn a-btn-sm a-btn-danger" @click="remove(preview)"><Trash2 :size="13" /> 删除</button>
            </div>
          </aside>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.upload-btn { cursor: pointer; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.search { width: min(320px, 100%); }
.toolbar-note { font-family: var(--font-mono); font-size: 11.5px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(188px, 1fr));
  gap: 16px;
}
.tile {
  margin: 0;
  overflow: hidden;
  background: var(--a-panel);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  box-shadow: var(--edge-light);
  transition: border-color 240ms ease, box-shadow 500ms var(--ease-out-expo), transform 600ms var(--ease-out-expo);
}
.tile:hover { border-color: var(--color-line-strong); box-shadow: var(--shadow-md), var(--edge-light); transform: translateY(-3px); }
.tile.is-skel { aspect-ratio: 1 / 1.18; padding: 10px; }
.tile-skel { width: 100%; height: 75%; border-radius: var(--a-radius-sm); }

/* 底图：主色 + 模糊的 LQIP，图片加载前后都有温度 */
.tile-img {
  position: relative;
  aspect-ratio: 1;
  overflow: hidden;
  background-size: cover;
  background-position: center;
}
.tile-img::before {
  content: "";
  position: absolute;
  inset: 0;
  background: color-mix(in oklab, var(--color-bg) 35%, transparent);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
}
.tile-img img {
  position: relative;
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 12px;
  opacity: 0;
  /* 与加载后的滤镜函数列表保持一致，才能平滑插值 */
  filter: blur(8px) drop-shadow(0 0 0 rgb(var(--shadow-rgb) / 0));
  transform: scale(1.04);
  transition: opacity 600ms var(--ease-out-quart), filter 700ms var(--ease-out-quart), transform 900ms var(--ease-out-expo);
}
.tile-img img.is-loaded { opacity: 1; filter: blur(0) drop-shadow(0 6px 14px rgb(var(--shadow-rgb) / calc(0.18 * var(--shadow-k)))); transform: none; }
.tile:hover .tile-img img.is-loaded { transform: scale(1.04); }

.tile-actions {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 8px;
  display: flex;
  justify-content: center;
  gap: 4px;
  padding: 4px;
  border-radius: var(--a-radius);
  background: color-mix(in oklab, var(--color-bg) 82%, transparent);
  box-shadow: var(--shadow-md);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  opacity: 0;
  transform: translate3d(0, 10px, 0);
  transition: opacity var(--a-dur) ease, transform var(--a-dur-md) var(--ease-out-expo);
}
.tile:hover .tile-actions,
.tile-actions:focus-within { opacity: 1; transform: none; }
@media (hover: none) { .tile-actions { opacity: 1; transform: none; } }
.tile-btn {
  flex: 1;
  display: grid;
  place-items: center;
  height: 30px;
  border-radius: var(--a-radius-sm);
  color: var(--color-ink-muted);
  transition: color 160ms ease, background-color 160ms ease;
}
.tile-btn:hover { color: var(--color-ink); background: var(--a-hover); }
.tile-btn.is-danger:hover { color: var(--a-danger); background: color-mix(in oklab, var(--a-danger) 12%, transparent); }

.tile-meta { display: flex; flex-direction: column; gap: 4px; padding: 10px 12px 12px; border-top: 1px solid var(--color-line); }
.tile-name { font-size: 12.5px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tile-sub { display: inline-flex; align-items: center; gap: 6px; font-size: 10.5px; color: var(--color-ink-faint); }
.tile-sub i { width: 8px; height: 8px; border-radius: 50%; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.15); }

/* 上传队列（右下角） */
.queue {
  position: fixed;
  left: 50%;
  bottom: 24px;
  z-index: 1150;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transform: translateX(-50%);
  pointer-events: none;
}
.queue-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: min(340px, calc(100vw - 40px));
  height: 40px;
  padding: 0 14px;
  overflow: hidden;
  font-size: 12.5px;
  color: var(--color-ink);
  background: color-mix(in oklab, var(--color-bg) 88%, transparent);
  border: 1px solid var(--color-line);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-lg);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
}
.queue-item.is-ok { color: var(--a-ok); }
.queue-item.is-err { color: var(--a-danger); }
.queue-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--color-ink); }
.queue-bar { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; }
.queue-bar i { display: block; height: 100%; background: currentColor; transform-origin: 0 50%; transform: scaleX(0.15); }
.is-up .queue-bar i { color: var(--color-accent); background: var(--color-accent); animation: indeterminate 1.2s var(--ease-in-out-quart) infinite; }
.is-ok .queue-bar i, .is-err .queue-bar i { transform: scaleX(1); transition: transform 400ms var(--ease-out-expo); }
@keyframes indeterminate {
  0% { transform: translateX(-30%) scaleX(0.3); }
  100% { transform: translateX(110%) scaleX(0.3); }
}

/* 整页拖放 */
.dropzone {
  position: fixed;
  inset: 0;
  z-index: 1180;
  display: grid;
  place-items: center;
  background: color-mix(in oklab, var(--color-bg) 72%, transparent);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  pointer-events: none;
}
.dropzone::before {
  content: "";
  position: absolute;
  inset: 18px;
  border: 1.5px dashed color-mix(in oklab, var(--color-accent) 70%, transparent);
  border-radius: var(--a-radius);
}
.dropzone-card { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--color-ink); }
.dropzone-ring {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  margin-bottom: 10px;
  border-radius: 50%;
  color: var(--color-accent);
  background: color-mix(in oklab, var(--color-accent) 12%, transparent);
  box-shadow: 0 0 0 10px color-mix(in oklab, var(--color-accent) 5%, transparent);
  animation: ring-bob 1.4s var(--ease-in-out-quart) infinite;
}
@keyframes ring-bob { 50% { transform: translateY(-6px); box-shadow: 0 0 0 16px color-mix(in oklab, var(--color-accent) 3%, transparent); } }
.dropzone-title { font-family: var(--font-serif); font-size: 22px; font-weight: 700; }
.dropzone-hint { font-size: 13px; color: var(--color-ink-muted); }
.drop-enter-active, .drop-leave-active { transition: opacity 220ms ease; }
.drop-enter-active .dropzone-card { transition: transform 520ms var(--ease-spring); }
.drop-enter-from, .drop-leave-to { opacity: 0; }
.drop-enter-from .dropzone-card { transform: scale(0.94); }

/* 灯箱 */
.lb {
  position: fixed;
  inset: 0;
  z-index: 1220;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  background: color-mix(in oklab, var(--color-bg) 92%, transparent);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
}
.lb-stage { display: grid; place-items: center; padding: 48px; min-width: 0; }
.lb-stage img { max-width: 100%; max-height: calc(100vh - 96px); object-fit: contain; border-radius: var(--a-radius-sm); box-shadow: var(--shadow-float); }
.lb-info {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 56px 24px 24px;
  background: var(--a-panel);
  border-left: 1px solid var(--color-line);
  color: var(--color-ink);
}
.lb-close { position: absolute; top: 14px; right: 14px; }
.lb-name { font-family: var(--font-serif); font-size: 17px; font-weight: 700; line-height: 1.45; overflow-wrap: anywhere; }
.lb-dl { display: flex; flex-direction: column; gap: 10px; font-size: 12.5px; }
.lb-dl div { display: flex; justify-content: space-between; gap: 12px; }
.lb-dl dt { color: var(--color-ink-faint); }
.lb-dl dd { display: inline-flex; align-items: center; gap: 6px; }
.lb-swatch { width: 10px; height: 10px; border-radius: 50%; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.15); }
.lb-url {
  padding: 10px 12px;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  background: var(--a-hover);
  border-radius: var(--a-radius-sm);
  overflow-wrap: anywhere;
}
.lb-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.lb-enter-active { transition: opacity 260ms ease; }
.lb-enter-active .lb-stage img { transition: transform 620ms var(--ease-spring), opacity 300ms ease; }
.lb-enter-active .lb-info { transition: transform 620ms var(--ease-out-expo); }
.lb-leave-active { transition: opacity 200ms ease; }
.lb-enter-from, .lb-leave-to { opacity: 0; }
.lb-enter-from .lb-stage img { transform: scale(0.94); opacity: 0; }
.lb-enter-from .lb-info { transform: translate3d(40px, 0, 0); }

@media (max-width: 760px) {
  .lb { grid-template-columns: 1fr; grid-template-rows: minmax(0, 1fr) auto; }
  .lb-info { border-left: 0; border-top: 1px solid var(--color-line); padding-top: 20px; }
  .lb-stage { padding: 20px; }
  .lb-stage img { max-height: 50vh; }
}

/* 衬底：纸面上 10% 的主色 + 浅网点，像图片放在一张校样纸上 */
.tile-img {
  background-color: color-mix(in oklab, var(--mat) 10%, var(--a-paper));
  background-image: radial-gradient(circle, color-mix(in oklab, var(--mat) 26%, transparent) 0.8px, transparent 1.1px);
  background-size: 6px 6px;
}
</style>
