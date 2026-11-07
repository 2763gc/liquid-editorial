<script setup lang="ts">
import { ref, computed } from 'vue';

interface LinkItem {
  id: number;
  name: string;
  url: string;
  avatar: string | null;
  description: string | null;
  category: string;
}

const { data: linksData } = await useFetch<LinkItem[]>('/api/v1/links', { default: () => [] });
const links = computed(() => linksData.value || []);

const SITE = [
  { k: '站名', v: "Luntrix's Editorial" },
  { k: '网址', v: 'https://luntrix.com' },
  { k: '简介', v: '杂志级排版 × 空间化交互 × 电影级动效个人技术博客' },
  { k: '头像', v: 'https://luntrix.com/avatar.png' },
];
const copied = ref('');
async function copy(k: string, v: string) {
  try {
    await navigator.clipboard.writeText(v);
    copied.value = k;
    setTimeout(() => { if (copied.value === k) copied.value = ''; }, 1600);
  } catch {}
}

function host(url: string) {
  return url.replace(/^https?:\/\//, '').replace(/\/$/, '');
}

useHead({
  title: "友链 · Luntrix's Editorial",
  meta: [{ name: 'description', content: '优秀同行、开源创造者与设计灵感来源的技术博客集合。' }],
});
</script>

<template>
  <div class="links-page">
    <UiPageMasthead
      index="09"
      en="Fellow Travelers"
      label="数字邻居"
      title="友链与同行"
      lede="数字荒原上的引路星光。专注于内核探究、前端设计美学与高质量随笔的技术写作者。"
      :stats="[{ label: 'Neighbors', value: links.length, unit: '位' }]"
    />

    <div class="page-shell">
      <div v-if="links.length" class="link-grid hairline-grid">
        <a
          v-for="link in links"
          :key="link.id"
          :href="link.url"
          target="_blank"
          rel="noopener noreferrer"
          class="link-card"
          data-cursor="open"
        >
          <span class="link-head">
            <span class="link-avatar">
              <img v-if="link.avatar" :src="link.avatar" :alt="''" loading="lazy">
              <span v-else>{{ link.name[0] }}</span>
            </span>
            <span class="link-who">
              <span class="link-name">{{ link.name }}</span>
              <span class="link-host">{{ host(link.url) }}</span>
            </span>
            <span class="link-arrow" aria-hidden="true">↗</span>
          </span>
          <span class="link-desc">{{ link.description || '一位低调的技术探索者' }}</span>
        </a>
      </div>

      <section class="apply" aria-labelledby="apply-title">
        <header class="apply-head">
          <span class="uses-no">Exchange</span>
          <h2 id="apply-title" class="apply-title">申请互换友链</h2>
          <p class="apply-sub">欢迎同为技术博客作者的同行建立链接。基本准则：长期原创更新、内容健康无过度商业广告、支持 HTTPS。</p>
          <p class="apply-sub">添加本站链接后，邮件联系 <a href="mailto:admin@example.com" class="link-draw">admin@example.com</a>，将在 24 小时内完成添加与回链。</p>
        </header>
        <dl class="apply-card">
          <div v-for="row in SITE" :key="row.k" class="apply-row">
            <dt>{{ row.k }}</dt>
            <dd>{{ row.v }}</dd>
            <button type="button" class="apply-copy" :class="{ 'is-copied': copied === row.k }" @click="copy(row.k, row.v)">
              {{ copied === row.k ? '已复制' : '复制' }}
            </button>
          </div>
        </dl>
      </section>
    </div>
  </div>
</template>

<style scoped>
.link-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: clamp(32px, 4vw, 56px);
}
.link-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 188px;
  padding: 24px;
  transition: background-color 500ms var(--ease-out-quart);
}
.link-card:hover { background: color-mix(in srgb, var(--color-bg) 96%, var(--color-ink)); }
.link-head { display: flex; align-items: center; gap: 14px; }
.link-avatar {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  overflow: hidden;
  background: var(--color-surface);
  box-shadow: 0 0 0 1px var(--color-line);
  font-family: var(--font-display);
  font-size: 18px;
  transition: transform 700ms var(--ease-spring);
}
.link-avatar img { width: 100%; height: 100%; object-fit: cover; }
.link-card:hover .link-avatar { transform: rotate(-8deg) scale(1.06); }
.link-who { display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1; }
.link-name { font-size: 15.5px; font-weight: 600; }
.link-host {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-ink-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-arrow {
  align-self: flex-start;
  color: var(--color-ink-faint);
  transition: transform 600ms var(--ease-out-expo), color var(--dur-sm) ease;
}
.link-card:hover .link-arrow { transform: translate(3px, -3px); color: var(--color-accent); }
.link-desc { font-family: var(--font-serif); font-size: 14.5px; line-height: 1.8; color: var(--color-ink-muted); }

.apply {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
  gap: clamp(24px, 4vw, 72px);
  margin-top: clamp(64px, 8vw, 120px);
  padding-top: clamp(32px, 4vw, 48px);
  border-top: 1px solid var(--color-ink);
}
.uses-no {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-accent);
}
.apply-title { margin-top: 10px; font-family: var(--font-serif); font-size: clamp(24px, 2.4vw, 34px); font-weight: 900; }
.apply-sub { margin-top: 14px; max-width: 30em; font-size: 14px; line-height: 1.85; color: var(--color-ink-muted); }

.apply-card {
  align-self: start;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  box-shadow: var(--edge-light);
}
.apply-row {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 14px 10px 14px 18px;
  font-family: var(--font-mono);
  font-size: 12px;
}
.apply-row + .apply-row { border-top: 1px solid var(--color-line); }
.apply-row dt { color: var(--color-ink-faint); }
.apply-row dd { overflow-wrap: anywhere; }
.apply-copy {
  height: 26px;
  padding: 0 10px;
  font-size: 11px;
  color: var(--color-ink-muted);
  border-radius: var(--radius-xs);
  transition: color var(--dur-micro) ease, background-color var(--dur-micro) ease;
}
.apply-copy:hover { color: var(--color-ink); background: color-mix(in oklab, var(--color-ink) 6%, transparent); }
.apply-copy.is-copied { color: var(--color-accent); }

@media (max-width: 980px) {
  .link-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .link-grid { grid-template-columns: 1fr; }
  .apply { grid-template-columns: 1fr; }
}
</style>
