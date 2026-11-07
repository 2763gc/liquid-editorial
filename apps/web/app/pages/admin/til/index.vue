<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Plus, PenLine, Trash2, Zap, Search } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';

definePageMeta({ layout: 'admin' });
useHead({ title: '今日所学 · 编辑部后台' });

interface TILItem { id: number; title: string; tag: string; content_md: string; created_at: string }

const toast = useToast();
const { confirm } = useConfirm();

const items = ref<TILItem[]>([]);
const loading = ref(true);
const activeTag = ref('');
const query = ref('');

const tags = computed(() => {
  const m = new Map<string, number>();
  for (const t of items.value) m.set(t.tag, (m.get(t.tag) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
});
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return items.value.filter((t) => (!activeTag.value || t.tag === activeTag.value) && (!q || `${t.title} ${t.content_md}`.toLowerCase().includes(q)));
});

async function load() {
  loading.value = true;
  try {
    const d = await adminFetch<any>('/api/v1/admin/til', { query: { page_size: 100 } });
    items.value = d.items || [];
  } catch (err) {
    toast.error('TIL 加载失败', apiErrorMessage(err));
  } finally {
    loading.value = false;
  }
}

/* ---- 新增 / 编辑抽屉 ---- */
const drawer = ref(false);
const editing = ref<TILItem | null>(null);
const form = ref({ title: '', tag: '', content_md: '' });
const errors = ref<Record<string, string>>({});
const submitting = ref(false);
const LIMIT = 800;

function openCreate() {
  editing.value = null;
  form.value = { title: '', tag: activeTag.value || '', content_md: '' };
  errors.value = {};
  drawer.value = true;
}
function openEdit(t: TILItem) {
  editing.value = t;
  form.value = { title: t.title, tag: t.tag, content_md: t.content_md };
  errors.value = {};
  drawer.value = true;
}

function validate() {
  const e: Record<string, string> = {};
  if (!form.value.title.trim()) e.title = '写一个能被搜索到的标题';
  if (!form.value.tag.trim()) e.tag = '至少一个标签，方便归类';
  if (!form.value.content_md.trim()) e.content_md = '内容不能为空';
  errors.value = e;
  return !Object.keys(e).length;
}

async function submit() {
  if (!validate()) return;
  submitting.value = true;
  const body = { title: form.value.title.trim(), tag: form.value.tag.trim().toLowerCase(), content_md: form.value.content_md };
  try {
    if (editing.value) {
      await adminFetch(`/api/v1/admin/til/${editing.value.id}`, { method: 'PUT', body });
      Object.assign(editing.value, body);
      toast.success('已更新', body.title);
    } else {
      await adminFetch('/api/v1/admin/til', { method: 'POST', body });
      toast.success('已发布', body.title);
      await load();
    }
    drawer.value = false;
  } catch (err) {
    toast.error('保存失败', apiErrorMessage(err));
  } finally {
    submitting.value = false;
  }
}

async function remove(t: TILItem) {
  const ok = await confirm({ title: '删除这条 TIL？', message: `「${t.title}」删除后无法恢复。`, confirmText: '删除', danger: true });
  if (!ok) return;
  try {
    await adminFetch(`/api/v1/admin/til/${t.id}`, { method: 'DELETE' });
    items.value = items.value.filter((x) => x.id !== t.id);
    toast.success('已删除', t.title);
  } catch (err) {
    toast.error('删除失败', apiErrorMessage(err));
  }
}

function onFormKey(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
}

onMounted(load);
</script>

<template>
  <div>
    <AdminPageHeader index="02" en="Today I Learned" title="今日所学" :description="`${items.length} 条知识切片 · ${tags.length} 个主题`">
      <button type="button" class="a-btn a-btn-accent" @click="openCreate"><Plus :size="15" :stroke-width="2" /> 新增 TIL</button>
    </AdminPageHeader>

    <div class="toolbar a-rise" style="--i: 1">
      <div class="tag-filter">
        <button type="button" class="a-chip" :class="{ 'is-on': !activeTag }" @click="activeTag = ''">全部 <span class="a-mono">{{ items.length }}</span></button>
        <button v-for="[t, n] in tags" :key="t" type="button" class="a-chip" :class="{ 'is-on': activeTag === t }" @click="activeTag = activeTag === t ? '' : t">#{{ t }} <span class="a-mono">{{ n }}</span></button>
      </div>
      <label class="a-input-icon search">
        <Search :size="15" :stroke-width="2" />
        <input v-model="query" type="search" class="a-input" placeholder="搜索标题或内容…" aria-label="搜索 TIL">
      </label>
    </div>

    <div v-if="loading" class="list">
      <div v-for="i in 4" :key="i" class="a-card til is-skel">
        <span class="a-skel" style="width: 60px" />
        <span class="a-skel" style="width: 55%; height: 16px; margin-top: 14px" />
        <span class="a-skel" style="width: 85%; margin-top: 12px" />
      </div>
    </div>

    <TransitionGroup v-else-if="filtered.length" tag="div" name="a-list" class="list">
      <article v-for="t in filtered" :key="t.id" class="a-card til">
        <header class="til-head">
          <span class="til-cmd"><b>$</b> til --tag <em>{{ t.tag }}</em></span>
          <time class="a-faint" :datetime="t.created_at">{{ timeAgo(t.created_at) }}</time>
        </header>
        <h2 class="til-title">{{ t.title }}</h2>
        <p class="til-excerpt">{{ plainText(t.content_md, 150) }}</p>
        <footer class="til-foot">
          <span class="a-faint a-mono">{{ t.content_md.length }} 字符</span>
          <span class="til-actions">
            <button type="button" class="a-btn a-btn-sm a-btn-quiet" @click="openEdit(t)"><PenLine :size="13" /> 编辑</button>
            <button type="button" class="a-icon-btn is-danger" aria-label="删除" title="删除" @click="remove(t)"><Trash2 :size="15" :stroke-width="1.75" /></button>
          </span>
        </footer>
      </article>
    </TransitionGroup>

    <div v-else class="a-card">
      <AdminEmpty :title="query || activeTag ? '没有匹配的记录' : '还没有 TIL'" hint="TIL 适合记录一个小发现：一条命令、一个 API 细节、一次踩坑。">
        <template #icon><Zap :size="20" :stroke-width="1.6" /></template>
        <button type="button" class="a-btn a-btn-accent" @click="openCreate"><Plus :size="14" /> 新增 TIL</button>
      </AdminEmpty>
    </div>

    <AdminDrawer :open="drawer" :title="editing ? '编辑 TIL' : '新增 TIL'" subtitle="一条小发现，五百字以内" @close="drawer = false">
      <form class="form" novalidate @submit.prevent="submit" @keydown="onFormKey">
        <div class="a-field">
          <label class="a-label" for="til-title">标题</label>
          <input id="til-title" v-model="form.title" class="a-input" type="text" placeholder="如：Vue 3.5 useId() 的生成规则" maxlength="120">
          <p v-if="errors.title" class="field-err">{{ errors.title }}</p>
        </div>
        <div class="a-field">
          <label class="a-label" for="til-tag">标签</label>
          <input id="til-tag" v-model="form.tag" class="a-input is-mono" type="text" placeholder="vue / rust / git" maxlength="32">
          <div v-if="tags.length" class="suggest">
            <button v-for="[t] in tags.slice(0, 10)" :key="t" type="button" class="a-chip" :class="{ 'is-on': form.tag === t }" @click="form.tag = t">#{{ t }}</button>
          </div>
          <p v-if="errors.tag" class="field-err">{{ errors.tag }}</p>
        </div>
        <div class="a-field">
          <label class="a-label" for="til-body">内容 <small :class="{ 'is-over': form.content_md.length > LIMIT }">{{ form.content_md.length }} / {{ LIMIT }}</small></label>
          <textarea id="til-body" v-model="form.content_md" class="a-textarea is-mono" rows="12" placeholder="支持 Markdown 与 ``` 代码块" />
          <span class="meter" aria-hidden="true"><i :style="{ transform: `scaleX(${Math.min(1, form.content_md.length / LIMIT)})` }" :class="{ 'is-over': form.content_md.length > LIMIT }" /></span>
          <p v-if="errors.content_md" class="field-err">{{ errors.content_md }}</p>
          <p v-else-if="form.content_md.length > LIMIT" class="a-hint">已经超过建议长度，篇幅较长的内容更适合写成特稿。</p>
        </div>
      </form>
      <template #footer>
        <span class="a-hint foot-hint"><kbd class="a-kbd">Ctrl</kbd> + <kbd class="a-kbd">↵</kbd> 保存</span>
        <button type="button" class="a-btn" @click="drawer = false">取消</button>
        <button type="button" class="a-btn a-btn-primary" :disabled="submitting" @click="submit">
          <span v-if="submitting" class="a-spin" />{{ editing ? '保存修改' : '发布' }}
        </button>
      </template>
    </AdminDrawer>
  </div>
</template>

<style scoped>
.toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.tag-filter { display: flex; flex-wrap: wrap; gap: 6px; }
.tag-filter .a-mono { font-size: 10px; opacity: 0.6; }
.search { width: min(280px, 100%); }

.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.til {
  display: flex;
  flex-direction: column;
  padding: 18px 20px 14px;
  transition: border-color 240ms ease, box-shadow 500ms var(--ease-out-expo), transform 600ms var(--ease-out-expo);
}
.til:not(.is-skel):hover { border-color: var(--color-line-strong); box-shadow: var(--shadow-md), var(--edge-light); transform: translateY(-2px); }
.til.is-skel { min-height: 170px; }
.til-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-family: var(--font-mono); font-size: 11.5px; }
.til-cmd { color: var(--color-ink-muted); }
.til-cmd b { color: var(--color-accent); margin-right: 4px; }
.til-cmd em { font-style: normal; color: var(--color-ink); }
.til-title { margin-top: 12px; font-family: var(--font-serif); font-size: 16.5px; font-weight: 700; line-height: 1.5; }
.til-excerpt { margin-top: 8px; font-size: 13px; line-height: 1.75; color: var(--color-ink-muted); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.til-foot { display: flex; align-items: center; justify-content: space-between; margin-top: auto; padding-top: 14px; font-size: 11px; }
.til-actions { display: inline-flex; align-items: center; gap: 2px; opacity: 0.4; transition: opacity 200ms ease; }
.til:hover .til-actions, .til-actions:focus-within { opacity: 1; }
@media (hover: none) { .til-actions { opacity: 1; } }

.form { display: flex; flex-direction: column; gap: 20px; }
.field-err { font-size: 12px; color: var(--a-danger); animation: err-in 400ms var(--ease-spring); }
@keyframes err-in { from { opacity: 0; transform: translateY(-3px); } }
.suggest { display: flex; flex-wrap: wrap; gap: 6px; }
.a-label small.is-over { color: var(--a-danger); }
.meter { display: block; height: 2px; border-radius: 2px; background: var(--a-hover); overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--color-ink-faint); transform-origin: 0 50%; transition: transform 300ms var(--ease-out-quart), background-color 200ms ease; }
.meter i.is-over { background: var(--a-danger); }
.foot-hint { margin-right: auto; }
</style>
