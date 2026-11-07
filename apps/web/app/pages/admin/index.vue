<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { PenLine, ExternalLink, ArrowUpRight } from 'lucide-vue-next';
import { adminFetch } from '~/composables/admin/useAdminApi';

definePageMeta({ layout: 'admin' });
useHead({ title: '仪表盘 · 编辑部后台' });

interface PostRow {
  id: number;
  number: number | null;
  title: string;
  status: string;
  view_count?: number;
  word_count?: number;
  reading_minutes?: number;
  published_at?: string | null;
  updated_at?: string | null;
}
interface HeatDay { date: string; published: number; updated: number }

const loading = ref(true);
const posts = ref<PostRow[]>([]);
const counts = ref({ total: 0, published: 0, draft: 0, til: 0, media: 0, links: 0 });
const integrations = ref<Record<string, boolean>>({});
const me = ref<{ display_name?: string } | null>(null);
const heat = ref<HeatDay[]>([]);

async function load() {
  loading.value = true;
  const [all, pub, draft, til, media, links, settings, user, heatmap] = await Promise.allSettled([
    adminFetch<{ items: PostRow[]; total: number }>('/api/v1/admin/posts', { query: { page_size: 100 } }),
    adminFetch<{ total: number }>('/api/v1/admin/posts', { query: { page_size: 1, status: 'published' } }),
    adminFetch<{ total: number }>('/api/v1/admin/posts', { query: { page_size: 1, status: 'draft' } }),
    adminFetch<{ total?: number; items?: unknown[] }>('/api/v1/admin/til', { query: { page_size: 1 } }),
    adminFetch<{ total: number }>('/api/v1/admin/media', { query: { page_size: 1 } }),
    adminFetch<unknown[]>('/api/v1/admin/links'),
    adminFetch<{ integrations?: Record<string, boolean> }>('/api/v1/admin/settings'),
    adminFetch<{ display_name?: string }>('/api/v1/admin/auth/me'),
    $fetch<{ days: HeatDay[] }>('/api/v1/stats/heatmap', { query: { days: 371 } }),
  ]);
  const val = <T,>(r: PromiseSettledResult<T>) => (r.status === 'fulfilled' ? r.value : null);
  posts.value = val(all)?.items || [];
  counts.value = {
    total: val(all)?.total ?? posts.value.length,
    published: val(pub)?.total ?? 0,
    draft: val(draft)?.total ?? 0,
    til: val(til)?.total ?? val(til)?.items?.length ?? 0,
    media: val(media)?.total ?? 0,
    links: val(links)?.length ?? 0,
  };
  integrations.value = val(settings)?.integrations || {};
  me.value = val(user);
  heat.value = val(heatmap)?.days || [];
  loading.value = false;
}

const greeting = computed(() => {
  const h = new Date().getHours();
  return h < 5 ? '夜深了' : h < 11 ? '早上好' : h < 14 ? '中午好' : h < 18 ? '下午好' : '晚上好';
});
const today = computed(() => {
  const d = new Date();
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · 星期${'日一二三四五六'[d.getDay()]}`;
});

const views = computed(() => posts.value.reduce((s, p) => s + (p.view_count || 0), 0));
const words = computed(() => posts.value.reduce((s, p) => s + (p.word_count || 0), 0));
const minutes = computed(() => posts.value.reduce((s, p) => s + (p.reading_minutes || 0), 0));
const publishedShare = computed(() => (counts.value.total ? counts.value.published / counts.value.total : 0));

type CalCell = (HeatDay & { level: number }) | null;
/*
 * 写作日历：最近 53 周，每周一列、每天一个墨点。首发记两分、修订记一分，越浓墨点越大，
 * 最浓的日子钤成朱砂方印。列首对齐到周日，和报纸的周历一致。
 */
const calendar = computed(() => {
  const days = heat.value;
  if (!days.length) return { weeks: [] as CalCell[][], months: [] as Array<{ col: number; label: string }>, total: 0, streak: 0, active: 0, revised: 0, longest: 0 };
  const pad = new Date(days[0].date).getDay();
  const cells: CalCell[] = Array.from({ length: pad }, () => null);
  for (const d of days) {
    const score = d.published * 2 + d.updated;
    cells.push({ ...d, level: score === 0 ? 0 : score === 1 ? 1 : score === 2 ? 2 : score <= 4 ? 3 : 4 });
  }
  const weeks: CalCell[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  const months: Array<{ col: number; label: string }> = [];
  let lastMonth = -1;
  weeks.forEach((w, col) => {
    const firstDay = w.find(Boolean);
    if (!firstDay) return;
    const m = new Date(firstDay.date).getMonth();
    if (m !== lastMonth) {
      months.push({ col, label: `${m + 1}月` });
      lastMonth = m;
    }
  });
  // 连续落笔的天数（从今天往回数，今天还没写不算断）
  let streak = 0;
  for (let i = days.length - 1; i >= 0; i--) {
    if (days[i].published || days[i].updated) streak += 1;
    else if (i < days.length - 1) break;
  }
  const active = days.filter((d) => d.published || d.updated).length;
  const revised = days.reduce((s, d) => s + d.updated, 0);
  // 最长连续落笔
  let longest = 0;
  let run = 0;
  for (const d of days) {
    run = d.published || d.updated ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  return { weeks, months, total: days.reduce((s, d) => s + d.published, 0), streak, active, revised, longest };
});

const recent = computed(() =>
  [...posts.value].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''))).slice(0, 6),
);
const drafts = computed(() => posts.value.filter((p) => p.status === 'draft').slice(0, 5));
const popular = computed(() => [...posts.value].filter((p) => p.status === 'published').sort((a, b) => (b.view_count || 0) - (a.view_count || 0)).slice(0, 5));
const popularMax = computed(() => Math.max(1, ...popular.value.map((p) => p.view_count || 0)));

const SYSTEMS = [
  { key: 'cos', label: '腾讯云 COS', on: '云端直传', off: '本地降级' },
  { key: 'github', label: 'GitHub API', on: '已配置', off: '公开限额' },
  { key: 'smtp', label: 'SMTP 邮件', on: '已配置', off: '未配置' },
];

onMounted(load);
</script>

<template>
  <div class="dash">
    <AdminPageHeader index="00" en="Editor's Desk" :title="`${greeting}，${me?.display_name || '编辑'}`" :description="today">
      <a href="/" target="_blank" rel="noopener" class="a-btn"><ExternalLink :size="14" :stroke-width="1.5" /> 访问站点</a>
      <NuxtLink to="/admin/posts/new" class="a-btn a-btn-primary"><PenLine :size="14" :stroke-width="1.5" /> 撰写新特稿</NuxtLink>
    </AdminPageHeader>

    <!-- 本期数据：一条发丝线分隔的数字栏 -->
    <section class="kpis a-card a-rise" style="--i: 1" aria-label="本期数据">
      <div class="kpi">
        <p class="kpi-label">特稿</p>
        <p class="kpi-value"><AdminCountUp :value="counts.total" /></p>
        <div class="kpi-split" :title="`已发布 ${counts.published} / 草稿 ${counts.draft}`">
          <span class="kpi-split-bar" :style="{ transform: `scaleX(${publishedShare})` }" />
        </div>
        <p class="kpi-sub"><span class="a-status is-ok">{{ counts.published }} 已发布</span><span class="a-status is-warn">{{ counts.draft }} 草稿</span></p>
      </div>
      <div class="kpi">
        <p class="kpi-label">浏览</p>
        <p class="kpi-value"><AdminCountUp :value="views" /></p>
        <p class="kpi-sub a-faint">篇均 {{ counts.published ? Math.round(views / Math.max(1, counts.published)).toLocaleString() : 0 }} 次</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">字数</p>
        <p class="kpi-value"><AdminCountUp :value="words" /></p>
        <p class="kpi-sub a-faint">约 {{ minutes.toLocaleString() }} 分钟阅读</p>
      </div>
      <div class="kpi">
        <p class="kpi-label">素材</p>
        <div class="kpi-trio">
          <NuxtLink to="/admin/til"><b><AdminCountUp :value="counts.til" /></b><span>TIL</span></NuxtLink>
          <NuxtLink to="/admin/media"><b><AdminCountUp :value="counts.media" /></b><span>媒体</span></NuxtLink>
          <NuxtLink to="/admin/links"><b><AdminCountUp :value="counts.links" /></b><span>友链</span></NuxtLink>
        </div>
      </div>
    </section>

    <section class="grid">
      <!-- 写作日历 -->
      <div class="a-card span-8 a-rise" style="--i: 2">
        <header class="a-card-head">
          <div>
            <p class="a-card-title" data-no="01">写作日历</p>
            <p class="a-card-sub">最近一年首发 {{ calendar.total }} 篇<template v-if="calendar.streak"> · 连续 {{ calendar.streak }} 天落笔</template></p>
          </div>
          <span class="cal-legend" aria-hidden="true">淡<i v-for="l in 5" :key="l" :class="`lv-${l - 1}`" />浓</span>
        </header>
        <div class="cal" :class="{ 'is-loading': loading }">
          <div class="cal-months" aria-hidden="true">
            <span v-for="m in calendar.months" :key="m.col" :style="{ gridColumn: m.col + 1 }">{{ m.label }}</span>
          </div>
          <div class="cal-grid" role="img" :aria-label="`最近一年首发 ${calendar.total} 篇`">
            <div v-for="(w, wi) in calendar.weeks" :key="wi" class="cal-week" :style="{ '--w': wi }">
              <span
                v-for="(d, di) in w"
                :key="di"
                class="cal-day"
                :class="d ? `lv-${d.level}` : 'is-void'"
                :title="d ? `${d.date} · 首发 ${d.published} · 修订 ${d.updated}` : undefined"
              />
            </div>
          </div>
          <dl class="cal-stats">
            <div><dt>首发</dt><dd>{{ calendar.total }}<small>篇</small></dd></div>
            <div><dt>修订</dt><dd>{{ calendar.revised }}<small>次</small></dd></div>
            <div><dt>落笔</dt><dd>{{ calendar.active }}<small>天</small></dd></div>
            <div><dt>最长连续</dt><dd>{{ calendar.longest }}<small>天</small></dd></div>
          </dl>
        </div>
      </div>

      <!-- 热门 -->
      <div class="a-card span-4 a-rise" style="--i: 3">
        <header class="a-card-head">
          <div>
            <p class="a-card-title" data-no="02">热门特稿</p>
            <p class="a-card-sub">按累计浏览</p>
          </div>
        </header>
        <ol v-if="popular.length" class="pop">
          <li v-for="(p, i) in popular" :key="p.id">
            <NuxtLink :to="`/admin/posts/${p.id}`" class="pop-row">
              <span class="pop-rank">{{ i + 1 }}</span>
              <span class="pop-main">
                <span class="pop-title">{{ p.title }}</span>
                <span class="pop-bar"><i :style="{ transform: `scaleX(${(p.view_count || 0) / popularMax})`, '--i': i }" /></span>
              </span>
              <span class="pop-views a-mono">{{ (p.view_count || 0).toLocaleString() }}</span>
            </NuxtLink>
          </li>
        </ol>
        <p v-else class="card-empty">还没有读者留下足迹。</p>
      </div>

      <!-- 最近编辑 -->
      <div class="a-card span-8 a-rise" style="--i: 4">
        <header class="a-card-head">
          <div>
            <p class="a-card-title" data-no="03">最近编辑</p>
            <p class="a-card-sub">按最后修改时间</p>
          </div>
          <NuxtLink to="/admin/posts" class="a-btn a-btn-sm a-btn-quiet">全部特稿 <ArrowUpRight :size="13" :stroke-width="1.5" /></NuxtLink>
        </header>
        <ul v-if="loading" class="recent">
          <li v-for="i in 4" :key="i" class="recent-skel"><span class="a-skel" style="width: 56px" /><span class="a-skel" :style="{ width: `${40 + i * 9}%` }" /></li>
        </ul>
        <ul v-else class="recent">
          <li v-for="p in recent" :key="p.id">
            <NuxtLink :to="`/admin/posts/${p.id}`" class="recent-row">
              <span class="a-mono recent-no">No.{{ issueNo(p.number) }}</span>
              <span class="recent-title">{{ p.title }}</span>
              <span class="a-status" :class="p.status === 'published' ? 'is-ok' : 'is-warn'">{{ p.status === 'published' ? '已发布' : '草稿' }}</span>
              <span class="recent-time a-faint">{{ timeAgo(p.updated_at) }}</span>
              <ArrowUpRight class="recent-go" :size="14" :stroke-width="1.5" />
            </NuxtLink>
          </li>
        </ul>
      </div>

      <div class="span-4 stack">
        <!-- 草稿箱 -->
        <div class="a-card a-rise" style="--i: 5">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="04">草稿箱</p>
              <p class="a-card-sub">{{ counts.draft }} 篇待完成</p>
            </div>
          </header>
          <ul v-if="drafts.length" class="drafts">
            <li v-for="p in drafts" :key="p.id">
              <NuxtLink :to="`/admin/posts/${p.id}`" class="draft-row">
                <span class="draft-title">{{ p.title }}</span>
                <span class="a-faint a-mono">{{ p.word_count || 0 }} 字</span>
              </NuxtLink>
            </li>
          </ul>
          <p v-else class="card-empty">没有积压的草稿，干净利落。</p>
        </div>

        <!-- 系统 -->
        <div class="a-card a-rise" style="--i: 6">
          <header class="a-card-head">
            <div>
              <p class="a-card-title" data-no="05">系统集成</p>
              <p class="a-card-sub">只显示状态，不回显密钥</p>
            </div>
          </header>
          <ul class="systems">
            <li v-for="s in SYSTEMS" :key="s.key">
              <span>{{ s.label }}</span>
              <span class="leader" aria-hidden="true" />
              <span class="a-status" :class="integrations[s.key] ? 'is-ok' : ''">{{ integrations[s.key] ? s.on : s.off }}</span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ---------------- 本期数据 ---------------- */
.kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.kpi { display: flex; flex-direction: column; gap: 10px; padding: 18px 22px 20px; min-height: 150px; }
.kpi + .kpi { border-left: 1px solid var(--color-line); }
.kpi-label { font-family: var(--font-serif); font-size: 13px; font-weight: 700; letter-spacing: 0.12em; color: var(--color-ink-muted); }
.kpi-value {
  font-family: var(--font-display);
  font-size: clamp(36px, 3.4vw, 48px);
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums lining-nums;
  font-variation-settings: "opsz" 96, "SOFT" 50;
}
.kpi-sub { display: flex; flex-wrap: wrap; gap: 12px; margin-top: auto; font-size: 12px; }
.kpi-split { position: relative; height: 1px; background: var(--color-line-strong); }
.kpi-split-bar {
  position: absolute;
  inset: -1px 0;
  display: block;
  background: var(--a-ok);
  transform-origin: 0 50%;
  transition: transform 900ms var(--ease-out-expo) 120ms;
}
.kpi-trio { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: auto; border-top: 1px solid var(--color-line); }
.kpi-trio a {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 0 0;
  transition: color var(--a-dur) ease;
}
.kpi-trio a + a { padding-left: 14px; border-left: 1px solid var(--color-line); }
.kpi-trio b { font-family: var(--font-display); font-size: 26px; font-weight: 500; line-height: 1; font-variant-numeric: tabular-nums; }
.kpi-trio span { font-size: 11.5px; color: var(--color-ink-faint); }
.kpi-trio a:hover span { color: var(--color-ink); }

/* ---------------- 栅格 ---------------- */
.grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.span-8 { grid-column: span 8; }
.span-4 { grid-column: span 4; }
.stack { display: flex; flex-direction: column; gap: 16px; }
.card-empty { padding: 28px 18px; font-size: 13px; color: var(--color-ink-faint); }

/* ---------------- 写作日历 ---------------- */
.cal { padding: 16px 18px 20px; overflow-x: auto; }
.cal-months {
  display: grid;
  grid-template-columns: repeat(53, 12px);
  gap: 3px;
  height: 16px;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-ink-faint);
}
.cal-months span { white-space: nowrap; }
.cal-grid { display: grid; grid-auto-flow: column; grid-auto-columns: 12px; gap: 3px; }
.cal-week { display: grid; grid-template-rows: repeat(7, 12px); gap: 3px; }
.cal-day {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: color-mix(in oklab, var(--color-ink) 9%, transparent);
  transform: scale(0.42);
  transition: transform var(--a-dur-md) var(--ease-out-back);
}
.cal-day.is-void { visibility: hidden; }
/* 墨点：越浓越大；最浓的日子钤成朱砂方印 */
.cal-day.lv-1 { background: color-mix(in oklab, var(--color-ink) 35%, transparent); transform: scale(0.6); }
.cal-day.lv-2 { background: color-mix(in oklab, var(--color-ink) 60%, transparent); transform: scale(0.75); }
.cal-day.lv-3 { background: var(--color-ink); transform: scale(0.88); }
.cal-day.lv-4 { background: var(--color-seal); transform: scale(1); border-radius: 2px; }
.cal-day:not(.is-void):hover { transform: scale(1.25); }
.cal.is-loading .cal-grid { opacity: 0.3; }
.cal-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin-top: 22px; border-top: 1px solid var(--color-line); }
.cal-stats div { display: flex; flex-direction: column; gap: 4px; padding: 14px 0 0; }
.cal-stats div + div { padding-left: 16px; border-left: 1px solid var(--color-line); }
.cal-stats dt { font-size: 11.5px; color: var(--color-ink-faint); }
.cal-stats dd { font-family: var(--font-display); font-size: 24px; font-weight: 500; line-height: 1; font-variant-numeric: tabular-nums; }
.cal-stats small { margin-left: 3px; font-family: var(--font-sans); font-size: 11px; color: var(--color-ink-muted); }
.cal-legend { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--color-ink-faint); }
.cal-legend i { width: 10px; height: 10px; border-radius: 50%; background: color-mix(in oklab, var(--color-ink) 9%, transparent); }
.cal-legend .lv-1 { background: color-mix(in oklab, var(--color-ink) 35%, transparent); }
.cal-legend .lv-2 { background: color-mix(in oklab, var(--color-ink) 60%, transparent); }
.cal-legend .lv-3 { background: var(--color-ink); }
.cal-legend .lv-4 { background: var(--color-seal); border-radius: 2px; }
html.motion-ready .cal-week { animation: a-rise var(--a-dur-lg) var(--ease-out-expo) backwards; animation-delay: calc(var(--w) * 5ms + 100ms); }

/* ---------------- 热门 ---------------- */
.pop { list-style: none; padding: 6px 18px 14px; }
.pop-row { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--color-line); }
.pop li:last-child .pop-row { border-bottom: 0; }
.pop-rank { font-family: var(--font-display); font-size: 20px; font-style: italic; font-weight: 300; color: var(--color-ink-faint); font-variation-settings: "opsz" 48, "SOFT" 100; }
.pop li:first-child .pop-rank { color: var(--color-seal); }
.pop-main { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.pop-title { font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: transform var(--a-dur-md) var(--ease-out-expo); }
.pop-row:hover .pop-title { transform: translateX(3px); }
.pop-bar { position: relative; height: 1px; background: var(--color-line); }
.pop-bar i { position: absolute; inset: -0.5px 0; background: var(--color-ink); transform-origin: 0 50%; animation: pop-in 900ms var(--ease-out-expo) backwards; animation-delay: calc(var(--i) * 40ms + 200ms); }
@keyframes pop-in { from { transform: scaleX(0); } }
.pop-views { font-size: 11.5px; color: var(--color-ink-muted); }

/* ---------------- 最近编辑 ---------------- */
.recent { list-style: none; padding: 4px 0; }
.recent-row {
  position: relative;
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr) auto 72px 16px;
  align-items: center;
  gap: 14px;
  height: 46px;
  padding: 0 18px;
  font-size: 13px;
  transition: background-color var(--a-dur) ease;
}
.recent-row::before { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 2px; background: var(--color-ink); transform: scaleY(0); transition: transform var(--a-dur-md) var(--ease-out-expo); }
.recent-row:hover { background: var(--a-hover); }
.recent-row:hover::before { transform: scaleY(1); }
.recent-no { font-size: 11px; color: var(--color-accent-text); }
.recent-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-time { font-size: 11.5px; text-align: right; }
.recent-go { color: var(--color-ink-faint); opacity: 0; transform: translate(-4px, 4px); transition: opacity var(--a-dur) ease, transform var(--a-dur-md) var(--ease-out-expo); }
.recent-row:hover .recent-go { opacity: 1; transform: none; }
.recent-skel { display: flex; align-items: center; gap: 16px; height: 46px; padding: 0 18px; }

/* ---------------- 草稿 / 系统 ---------------- */
.drafts, .systems { list-style: none; padding: 4px 18px 10px; }
.draft-row { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; font-size: 13px; border-bottom: 1px solid var(--color-line); }
.drafts li:last-child .draft-row { border-bottom: 0; }
.draft-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color var(--a-dur) ease; }
.draft-row:hover .draft-title { color: var(--color-accent-text); }
.systems li { display: flex; align-items: baseline; padding: 10px 0; font-size: 13px; border-bottom: 1px solid var(--color-line); }
.systems li:last-child { border-bottom: 0; }

@media (max-width: 1100px) {
  .span-8, .span-4 { grid-column: span 12; }
}
@media (max-width: 760px) {
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kpi:nth-child(3) { border-left: 0; }
  .kpi:nth-child(n + 3) { border-top: 1px solid var(--color-line); }
  .recent-row { grid-template-columns: 56px minmax(0, 1fr) auto; }
  .recent-time, .recent-go { display: none; }
}
</style>
