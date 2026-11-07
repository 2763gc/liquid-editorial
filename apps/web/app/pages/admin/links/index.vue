<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Plus, PenLine, Trash2, Link2, ExternalLink } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';

definePageMeta({ layout: 'admin' });
useHead({ title: '友链 · 编辑部后台' });

interface FriendLink {
  id: number;
  name: string;
  url: string;
  avatar: string | null;
  description: string | null;
  category: string;
  sort_order: number;
  is_active: number;
}

const toast = useToast();
const { confirm } = useConfirm();

const CATEGORIES: Record<string, string> = { tech: '同行技术', inspiration: '灵感思考', friend: '好友' };

const links = ref<FriendLink[]>([]);
const loading = ref(true);
const category = ref('');
const toggling = ref<number | null>(null);

const categoryOptions = computed(() => [
  { value: '', label: '全部', count: links.value.length },
  ...Object.entries(CATEGORIES).map(([value, label]) => ({ value, label, count: links.value.filter((l) => l.category === value).length })),
]);
const filtered = computed(() => (category.value ? links.value.filter((l) => l.category === category.value) : links.value));
const activeCount = computed(() => links.value.filter((l) => l.is_active).length);

function host(url: string) {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

async function load() {
  loading.value = true;
  try {
    links.value = await adminFetch<FriendLink[]>('/api/v1/admin/links');
  } catch (err) {
    toast.error('友链加载失败', apiErrorMessage(err));
  } finally {
    loading.value = false;
  }
}

function toPayload(l: Partial<FriendLink>) {
  return {
    name: l.name || '',
    url: l.url || '',
    avatar: l.avatar || null,
    description: l.description || null,
    category: l.category || 'tech',
    sort_order: Number(l.sort_order) || 0,
    is_active: l.is_active ? 1 : 0,
  };
}

/** 开关即时保存，失败回滚 */
async function toggleActive(l: FriendLink, on: boolean) {
  const prev = l.is_active;
  l.is_active = on ? 1 : 0;
  toggling.value = l.id;
  try {
    await adminFetch(`/api/v1/admin/links/${l.id}`, { method: 'PUT', body: toPayload(l) });
    toast.success(on ? '已在前台展示' : '已从前台隐藏', l.name);
  } catch (err) {
    l.is_active = prev;
    toast.error('更新失败', apiErrorMessage(err));
  } finally {
    toggling.value = null;
  }
}

/* ---- 抽屉表单 ---- */
const drawer = ref(false);
const editing = ref<FriendLink | null>(null);
const form = ref(toPayload({}));
const errors = ref<Record<string, string>>({});
const submitting = ref(false);
const avatarOk = ref(true);

function openCreate() {
  editing.value = null;
  form.value = { ...toPayload({ category: category.value || 'tech', is_active: 1 }), sort_order: links.value.length };
  errors.value = {};
  avatarOk.value = true;
  drawer.value = true;
}
function openEdit(l: FriendLink) {
  editing.value = l;
  form.value = toPayload(l);
  errors.value = {};
  avatarOk.value = true;
  drawer.value = true;
}

function validate() {
  const e: Record<string, string> = {};
  if (!form.value.name.trim()) e.name = '请填写站点或博主名称';
  if (!/^https?:\/\/\S+\.\S+/.test(form.value.url.trim())) e.url = '请填写以 http(s):// 开头的完整网址';
  if (form.value.avatar && !/^https?:\/\//.test(form.value.avatar)) e.avatar = '头像需要是 http(s) 图片链接';
  errors.value = e;
  return !Object.keys(e).length;
}

async function submit() {
  if (!validate()) return;
  submitting.value = true;
  const body = { ...form.value, name: form.value.name.trim(), url: form.value.url.trim() };
  try {
    if (editing.value) {
      await adminFetch(`/api/v1/admin/links/${editing.value.id}`, { method: 'PUT', body });
      Object.assign(editing.value, body);
      toast.success('已更新', body.name);
    } else {
      await adminFetch('/api/v1/admin/links', { method: 'POST', body });
      toast.success('已添加', body.name);
      await load();
    }
    drawer.value = false;
  } catch (err) {
    toast.error('保存失败', apiErrorMessage(err));
  } finally {
    submitting.value = false;
  }
}

async function remove(l: FriendLink) {
  const ok = await confirm({ title: '删除这条友链？', message: `「${l.name}」将从友链页移除。`, confirmText: '删除', danger: true });
  if (!ok) return;
  try {
    await adminFetch(`/api/v1/admin/links/${l.id}`, { method: 'DELETE' });
    links.value = links.value.filter((x) => x.id !== l.id);
    toast.success('已删除', l.name);
  } catch (err) {
    toast.error('删除失败', apiErrorMessage(err));
  }
}

onMounted(load);
</script>

<template>
  <div>
    <AdminPageHeader index="04" en="Links" title="友链" :description="`${links.length} 位数字邻居 · ${activeCount} 位正在前台展示`">
      <button type="button" class="a-btn a-btn-accent" @click="openCreate"><Plus :size="15" :stroke-width="2" /> 新增友链</button>
    </AdminPageHeader>

    <div class="toolbar a-rise" style="--i: 1">
      <UiSegmented v-model="category" :options="categoryOptions" aria-label="按分类筛选" />
    </div>

    <div class="a-table-wrap a-rise" style="--i: 2">
      <table class="a-table">
        <thead>
          <tr>
            <th>站点</th>
            <th>简介</th>
            <th>分类</th>
            <th class="is-num">排序</th>
            <th>展示</th>
            <th class="is-actions"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody v-if="loading">
          <tr v-for="i in 4" :key="i">
            <td><span class="who"><span class="a-skel" style="width: 32px; height: 32px; border-radius: 50%" /><span class="a-skel" style="width: 120px" /></span></td>
            <td><span class="a-skel" style="width: 70%" /></td>
            <td><span class="a-skel" style="width: 56px" /></td>
            <td><span class="a-skel" style="width: 20px; margin-left: auto" /></td>
            <td><span class="a-skel" style="width: 40px; height: 22px" /></td>
            <td />
          </tr>
        </tbody>
        <TransitionGroup v-else tag="tbody" name="a-list">
          <tr v-for="l in filtered" :key="l.id" :class="{ 'is-off': !l.is_active }">
            <td>
              <span class="who">
                <span class="avatar">
                  <img v-if="l.avatar" :src="l.avatar" alt="" loading="lazy">
                  <template v-else>{{ l.name.slice(0, 1) }}</template>
                </span>
                <span class="who-text">
                  <span class="who-name">{{ l.name }}</span>
                  <a :href="l.url" target="_blank" rel="noopener" class="who-host a-mono">{{ host(l.url) }} <ExternalLink :size="10" /></a>
                </span>
              </span>
            </td>
            <td class="desc a-muted">{{ l.description || '—' }}</td>
            <td><span class="a-chip">{{ CATEGORIES[l.category] || l.category }}</span></td>
            <td class="is-num">{{ l.sort_order }}</td>
            <td><AdminSwitch :model-value="!!l.is_active" :disabled="toggling === l.id" :label="`在前台展示 ${l.name}`" @update:model-value="(v) => toggleActive(l, v)" /></td>
            <td class="is-actions">
              <span class="a-row-actions">
                <button type="button" class="a-icon-btn" title="编辑" aria-label="编辑" @click="openEdit(l)"><PenLine :size="15" :stroke-width="1.75" /></button>
                <button type="button" class="a-icon-btn is-danger" title="删除" aria-label="删除" @click="remove(l)"><Trash2 :size="15" :stroke-width="1.75" /></button>
              </span>
            </td>
          </tr>
        </TransitionGroup>
      </table>
      <AdminEmpty v-if="!loading && !filtered.length" title="还没有友链" hint="和同行互相链接，是独立博客之间最古老的礼节。">
        <template #icon><Link2 :size="20" :stroke-width="1.6" /></template>
        <button type="button" class="a-btn a-btn-accent" @click="openCreate"><Plus :size="14" /> 新增友链</button>
      </AdminEmpty>
    </div>

    <AdminDrawer :open="drawer" :title="editing ? '编辑友链' : '新增友链'" subtitle="展示在前台 /links 页面" @close="drawer = false">
      <div class="preview-card">
        <span class="avatar is-lg">
          <img v-if="form.avatar && avatarOk" :src="form.avatar" alt="" @error="avatarOk = false">
          <template v-else>{{ (form.name || '?').slice(0, 1) }}</template>
        </span>
        <span class="who-text">
          <span class="who-name">{{ form.name || '站点名称' }}</span>
          <span class="who-host a-mono">{{ form.url ? host(form.url) : 'example.com' }}</span>
          <span class="preview-desc">{{ form.description || '一句话简介会显示在这里。' }}</span>
        </span>
      </div>

      <div class="a-field">
        <label class="a-label" for="ln-name">名称</label>
        <input id="ln-name" v-model="form.name" class="a-input" type="text" placeholder="如：Dan Abramov" maxlength="60">
        <p v-if="errors.name" class="field-err">{{ errors.name }}</p>
      </div>
      <div class="a-field">
        <label class="a-label" for="ln-url">网址</label>
        <input id="ln-url" v-model="form.url" class="a-input is-mono" type="url" placeholder="https://">
        <p v-if="errors.url" class="field-err">{{ errors.url }}</p>
      </div>
      <div class="a-field">
        <label class="a-label" for="ln-avatar">头像 <small>可选</small></label>
        <input id="ln-avatar" v-model="form.avatar" class="a-input is-mono" type="url" placeholder="https://…/avatar.png" @input="avatarOk = true">
        <p v-if="errors.avatar" class="field-err">{{ errors.avatar }}</p>
      </div>
      <div class="a-field">
        <label class="a-label" for="ln-desc">简介</label>
        <textarea id="ln-desc" v-model="form.description" class="a-textarea" rows="3" placeholder="一句话介绍这位同行" maxlength="120" />
      </div>
      <div class="row-2">
        <div class="a-field">
          <label class="a-label" for="ln-cat">分类</label>
          <select id="ln-cat" v-model="form.category" class="a-select">
            <option v-for="(label, key) in CATEGORIES" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>
        <div class="a-field">
          <label class="a-label" for="ln-sort">排序 <small>越小越靠前</small></label>
          <input id="ln-sort" v-model.number="form.sort_order" class="a-input is-mono" type="number" min="0">
        </div>
      </div>
      <div class="flag">
        <div>
          <p class="flag-title">在前台展示</p>
          <p class="a-hint">关闭后保留记录，但不出现在友链页</p>
        </div>
        <AdminSwitch :model-value="!!form.is_active" label="在前台展示" @update:model-value="(v) => (form.is_active = v ? 1 : 0)" />
      </div>

      <template #footer>
        <button type="button" class="a-btn" @click="drawer = false">取消</button>
        <button type="button" class="a-btn a-btn-primary" :disabled="submitting" @click="submit">
          <span v-if="submitting" class="a-spin" />{{ editing ? '保存修改' : '添加' }}
        </button>
      </template>
    </AdminDrawer>
  </div>
</template>

<style scoped>
.toolbar { margin-bottom: 18px; }
.who { display: flex; align-items: center; gap: 12px; }
.avatar {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  overflow: hidden;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 14px;
  background: var(--a-hover);
  box-shadow: 0 0 0 1px var(--color-line);
}
.avatar.is-lg { width: 52px; height: 52px; font-size: 22px; }
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.who-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.who-name { font-size: 13.5px; font-weight: 600; }
.who-host { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-faint); transition: color 200ms ease; }
a.who-host:hover { color: var(--color-accent); }
.desc { max-width: 28em; font-size: 12.5px; line-height: 1.6; }
tr.is-off td:not(:nth-child(5)):not(.is-actions) { opacity: 0.45; }
tr td { transition: opacity 300ms ease; }

.preview-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border: 1px dashed var(--color-line-strong);
  border-radius: var(--a-radius);
}
.preview-desc { margin-top: 4px; font-size: 12.5px; color: var(--color-ink-muted); }
.field-err { font-size: 12px; color: var(--a-danger); animation: err-in 400ms var(--ease-spring); }
@keyframes err-in { from { opacity: 0; transform: translateY(-3px); } }
.row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.flag { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid var(--color-line); border-radius: var(--a-radius); }
.flag-title { font-size: 13.5px; font-weight: 600; }

@media (max-width: 760px) {
  .a-table th:nth-child(2), .a-table td:nth-child(2),
  .a-table th:nth-child(4), .a-table td:nth-child(4) { display: none; }
}
</style>
