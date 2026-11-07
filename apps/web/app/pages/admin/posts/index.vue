<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { PenLine, Search, X, ExternalLink, Send, EyeOff, Trash2, FileText, ChevronLeft, ChevronRight } from 'lucide-vue-next';
import { adminFetch, apiErrorMessage } from '~/composables/admin/useAdminApi';
import { useToast } from '~/composables/admin/useToast';
import { useConfirm } from '~/composables/admin/useConfirm';
import { useRowCursor } from '~/composables/admin/useRowCursor';

definePageMeta({ layout: 'admin' });
useHead({ title: '特稿 · 编辑部后台' });

const toast = useToast();
const { confirm } = useConfirm();

const PAGE_SIZE = 20;
const posts = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref('');
const query = ref('');
const loading = ref(true);
const busy = ref<number | null>(null);
const counts = ref({ all: 0, published: 0, draft: 0 });

const LAYOUT: Record<string, string> = { standard: '标准', wide: '宽幅', immersive: '沉浸', essay: '随笔', showcase: '作品' };

const statusOptions = computed(() => [
  { value: '', label: '全部', count: counts.value.all },
  { value: 'published', label: '已发布', count: counts.value.published },
  { value: 'draft', label: '草稿', count: counts.value.draft },
]);
const pages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)));

async function loadCounts() {
  const [a, p, d] = await Promise.allSettled([
    adminFetch<any>('/api/v1/admin/posts', { query: { page_size: 1 } }),
    adminFetch<any>('/api/v1/admin/posts', { query: { page_size: 1, status: 'published' } }),
    adminFetch<any>('/api/v1/admin/posts', { query: { page_size: 1, status: 'draft' } }),
  ]);
  const t = (r: PromiseSettledResult<any>) => (r.status === 'fulfilled' ? r.value.total : 0);
  counts.value = { all: t(a), published: t(p), draft: t(d) };
}

let seq = 0;
async function load() {
  const id = ++seq;
  loading.value = true;
  try {
    const data = await adminFetch<any>('/api/v1/admin/posts', {
      query: { page: page.value, page_size: PAGE_SIZE, status: status.value || undefined, q: query.value.trim() || undefined },
    });
    if (id !== seq) return;
    posts.value = data.items || [];
    total.value = data.total || 0;
  } catch (err) {
    if (id === seq) toast.error('特稿列表加载失败', apiErrorMessage(err));
  } finally {
    if (id === seq) loading.value = false;
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined;
watch(query, () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { page.value = 1; load(); }, 280);
});
watch(status, () => { page.value = 1; load(); });
watch(page, load);

async function togglePublish(post: any) {
  busy.value = post.id;
  const publishing = post.status !== 'published';
  try {
    if (publishing) await adminFetch(`/api/v1/admin/posts/${post.id}/publish`, { method: 'POST' });
    else await adminFetch(`/api/v1/admin/posts/${post.id}`, { method: 'PATCH', body: { status: 'draft' } });
    post.status = publishing ? 'published' : 'draft';
    if (publishing && !post.published_at) post.published_at = new Date().toISOString();
    toast.success(publishing ? '已发布' : '已撤回为草稿', post.title);
    loadCounts();
    if (status.value) load();
  } catch (err) {
    toast.error(publishing ? '发布失败' : '撤回失败', apiErrorMessage(err));
  } finally {
    busy.value = null;
  }
}

async function remove(post: any) {
  const ok = await confirm({
    title: '移入回收站？',
    message: `「${post.title}」将从前台下线并移入回收站，可在数据库中恢复。`,
    confirmText: '移入回收站',
    danger: true,
  });
  if (!ok) return;
  try {
    await adminFetch(`/api/v1/admin/posts/${post.id}`, { method: 'DELETE' });
    posts.value = posts.value.filter((p) => p.id !== post.id);
    total.value -= 1;
    toast.success('已移入回收站', post.title);
    loadCounts();
  } catch (err) {
    toast.error('删除失败', apiErrorMessage(err));
  }
}

/* 键盘：j / k 移动，回车编辑，o 前台查看，p 发布 / 撤回，/ 搜索 */
const router = useRouter();
const tableRef = ref<HTMLElement | null>(null);
const { cursor } = useRowCursor(posts, {
  scope: tableRef,
  searchSelector: '.search input',
  onOpen: (p) => router.push(`/admin/posts/${p.id}`),
  actions: {
    o: (p) => { if (p.status === 'published') window.open(`/posts/${p.slug}`, '_blank', 'noopener'); },
    p: (p) => togglePublish(p),
  },
});

onMounted(() => {
  load();
  loadCounts();
});
</script>

<template>
  <div>
    <AdminPageHeader index="01" en="Posts" title="特稿">
      <template #description>共 {{ counts.all }} 篇 · 已发布 {{ counts.published }} · 草稿 {{ counts.draft }}</template>
      <NuxtLink to="/admin/posts/new" class="a-btn a-btn-primary"><PenLine :size="14" :stroke-width="1.5" /> 撰写新特稿</NuxtLink>
    </AdminPageHeader>

    <div class="toolbar a-rise" style="--i: 1">
      <UiSegmented v-model="status" :options="statusOptions" aria-label="按状态筛选" />
      <label class="a-input-icon search">
        <Search :size="15" :stroke-width="2" />
        <input v-model="query" type="search" class="a-input" placeholder="搜索标题…  /" aria-label="搜索特稿标题">
        <button v-if="query" type="button" class="search-clear" aria-label="清空搜索" @click="query = ''"><X :size="13" /></button>
      </label>
      <p class="kbd-hint a-faint"><kbd class="a-kbd">j</kbd><kbd class="a-kbd">k</kbd> 移动 · <kbd class="a-kbd">↵</kbd> 编辑 · <kbd class="a-kbd">p</kbd> 发布 / 撤回 · <kbd class="a-kbd">o</kbd> 前台查看</p>
    </div>

    <div ref="tableRef" class="a-table-wrap a-rise" style="--i: 2">
      <table class="a-table">
        <thead>
          <tr>
            <th style="width: 84px">编号</th>
            <th>标题</th>
            <th>模板</th>
            <th>状态</th>
            <th>更新</th>
            <th class="is-num">字数</th>
            <th class="is-num">浏览</th>
            <th class="is-actions"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody v-if="loading && !posts.length">
          <tr v-for="i in 6" :key="`sk${i}`">
            <td><span class="a-skel" style="width: 52px" /></td>
            <td><span class="a-skel" :style="{ width: `${50 + (i % 3) * 14}%` }" /><span class="a-skel" style="width: 30%; height: 9px; margin-top: 8px" /></td>
            <td><span class="a-skel" style="width: 36px" /></td>
            <td><span class="a-skel" style="width: 58px; height: 22px" /></td>
            <td><span class="a-skel" style="width: 64px" /></td>
            <td><span class="a-skel" style="width: 40px; margin-left: auto" /></td>
            <td><span class="a-skel" style="width: 40px; margin-left: auto" /></td>
            <td />
          </tr>
        </tbody>
        <TransitionGroup v-else tag="tbody" name="a-list" :class="{ 'is-refreshing': loading }">
          <tr v-for="(post, idx) in posts" :key="post.id" :class="{ 'is-cursor': idx === cursor }" @mouseenter="cursor = idx">
            <td class="a-mono cell-no">No.{{ issueNo(post.number) }}</td>
            <td class="cell-title">
              <span class="cell-cover" aria-hidden="true"><InkCover :seed="post.slug" :no="post.number" :accent="post.accent_color" :width="96" :height="64" :numeral="false" :seal="false" /></span>
              <NuxtLink :to="`/admin/posts/${post.id}`" class="title-link">{{ post.title }}</NuxtLink>
              <span class="title-meta">
                <span class="a-mono a-faint slug" :title="`/posts/${post.slug}`">/{{ post.slug }}</span>
                <span v-for="t in (post.tags || []).slice(0, 3)" :key="t.id" class="a-chip"><i :style="{ color: t.color || 'var(--color-ink-faint)' }" />{{ t.name }}</span>
              </span>
            </td>
            <td class="a-muted cell-layout">{{ LAYOUT[post.layout_variant] || post.layout_variant }}</td>
            <td><span class="a-status" :class="post.status === 'published' ? 'is-ok' : 'is-warn'">{{ post.status === 'published' ? '已发布' : '草稿' }}</span></td>
            <td class="a-muted cell-time" :title="post.updated_at">{{ timeAgo(post.updated_at) }}</td>
            <td class="is-num">{{ (post.word_count || 0).toLocaleString() }}</td>
            <td class="is-num">{{ (post.view_count || 0).toLocaleString() }}</td>
            <td class="is-actions">
              <span class="a-row-actions">
                <a v-if="post.status === 'published'" :href="`/posts/${post.slug}`" target="_blank" rel="noopener" class="a-icon-btn" title="在前台查看" aria-label="在前台查看"><ExternalLink :size="15" :stroke-width="1.75" /></a>
                <NuxtLink :to="`/admin/posts/${post.id}`" class="a-icon-btn" title="编辑" aria-label="编辑"><PenLine :size="15" :stroke-width="1.75" /></NuxtLink>
                <button type="button" class="a-icon-btn" :title="post.status === 'published' ? '撤回为草稿' : '发布'" :aria-label="post.status === 'published' ? '撤回为草稿' : '发布'" :disabled="busy === post.id" @click="togglePublish(post)">
                  <span v-if="busy === post.id" class="a-spin" />
                  <EyeOff v-else-if="post.status === 'published'" :size="15" :stroke-width="1.75" />
                  <Send v-else :size="15" :stroke-width="1.75" />
                </button>
                <button type="button" class="a-icon-btn is-danger" title="移入回收站" aria-label="移入回收站" @click="remove(post)"><Trash2 :size="15" :stroke-width="1.75" /></button>
              </span>
            </td>
          </tr>
        </TransitionGroup>
      </table>

      <AdminEmpty v-if="!loading && !posts.length" :title="query ? `没有与「${query}」匹配的特稿` : '这里还没有特稿'" :hint="query ? '换个关键词试试，或清空搜索查看全部。' : '写下第一篇，它会出现在首页画布与文章索引里。'">
        <template #icon><FileText :size="20" :stroke-width="1.6" /></template>
        <button v-if="query" type="button" class="a-btn" @click="query = ''">清空搜索</button>
        <NuxtLink v-else to="/admin/posts/new" class="a-btn a-btn-primary"><PenLine :size="14" :stroke-width="1.5" /> 撰写新特稿</NuxtLink>
      </AdminEmpty>
    </div>

    <div v-if="pages > 1" class="a-pager">
      <span>第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 篇</span>
      <span class="a-pager-btns">
        <button type="button" class="a-btn a-btn-sm" :disabled="page <= 1" @click="page -= 1"><ChevronLeft :size="14" /> 上一页</button>
        <button type="button" class="a-btn a-btn-sm" :disabled="page >= pages" @click="page += 1">下一页 <ChevronRight :size="14" /></button>
      </span>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.search { width: min(320px, 100%); }
.search .a-input { padding-right: 32px; }
.search input::-webkit-search-cancel-button { display: none; }
.search-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: var(--a-radius-sm);
  color: var(--color-ink-muted);
  background: var(--a-hover);
}
.search-clear:hover { color: var(--color-ink); background: var(--a-press); }

tbody { transition: opacity var(--a-dur) ease; }
tbody.is-refreshing { opacity: 0.5; }
.cell-no { font-size: 11.5px; color: var(--color-accent-text); white-space: nowrap; }
.cell-title { position: relative; min-width: 280px; padding-left: 74px !important; }
.cell-cover { position: absolute; left: 14px; top: 50%; width: 48px; height: 32px; margin-top: -16px; overflow: hidden; border: 1px solid var(--color-line); }
.kbd-hint { flex-basis: 100%; display: flex; align-items: center; gap: 4px; font-size: 11.5px; }
@media (max-width: 860px) { .kbd-hint { display: none; } }
.title-link {
  display: inline-block;
  max-width: 38em;
  font-family: var(--font-serif);
  font-size: 14.5px;
  font-weight: 700;
  line-height: 1.45;
  transition: color 200ms ease;
}
.title-link:hover { color: var(--color-accent-text); }
.title-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 5px; font-size: 11px; }
.slug { max-width: 26ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 4px; }
.cell-layout, .cell-time { font-size: 12.5px; white-space: nowrap; }

@media (max-width: 860px) {
  .a-table th:nth-child(3), .a-table td:nth-child(3),
  .a-table th:nth-child(5), .a-table td:nth-child(5),
  .a-table th:nth-child(6), .a-table td:nth-child(6),
  .a-table th:nth-child(7), .a-table td:nth-child(7) { display: none; }
  .cell-title { min-width: 0; }
}
@media (max-width: 560px) {
  .a-table th:nth-child(1), .a-table td:nth-child(1) { display: none; }
  .cell-title { padding-left: 14px !important; }
  .cell-cover { display: none; }
  .title-link { font-size: 14px; }
  .slug { max-width: 18ch; }
}
</style>
