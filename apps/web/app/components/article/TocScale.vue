<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useLenis } from '~/composables/useLenis';

interface TocItem { level: number; text: string; anchor: string }

const props = defineProps<{ toc: TocItem[] }>();
const emit = defineEmits<{ (e: 'navigate', anchor: string): void }>();

const active = ref('');
const listRef = ref<HTMLElement | null>(null);
/** 当前章节标记（位置 / 高度）与已读填充高度，都只写 transform */
const marker = ref({ y: 0, h: 0, on: false });
const fill = ref(0);
const ready = ref(false);
const { scrollTo } = useLenis();
let io: IntersectionObserver | null = null;
let ro: ResizeObserver | null = null;
const visible = new Set<string>();

const activeIndex = computed(() => props.toc.findIndex((t) => t.anchor === active.value));

function setup() {
  io?.disconnect();
  visible.clear();
  const headings = props.toc
    .map((t) => document.getElementById(t.anchor))
    .filter((el): el is HTMLElement => !!el);
  if (!headings.length) return;
  // 视口上方 30% 区域作为「当前章节」判定带
  io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) visible.add(e.target.id);
        else visible.delete(e.target.id);
      }
      if (visible.size) {
        const first = props.toc.find((t) => visible.has(t.anchor));
        if (first) active.value = first.anchor;
      } else {
        // 没有标题在判定带内：取最后一个已经滚过的标题
        let current = '';
        for (const h of headings) {
          if (h.getBoundingClientRect().top < window.innerHeight * 0.3) current = h.id;
        }
        active.value = current;
      }
    },
    { rootMargin: '-80px 0px -70% 0px', threshold: 0 },
  );
  headings.forEach((h) => io!.observe(h));
}

function place() {
  const list = listRef.value;
  if (!list) return;
  const li = activeIndex.value >= 0 ? list.children[activeIndex.value] as HTMLElement | undefined : undefined;
  if (!li) {
    marker.value = { ...marker.value, on: false };
    fill.value = 0;
    return;
  }
  marker.value = { y: li.offsetTop, h: li.offsetHeight, on: true };
  fill.value = (li.offsetTop + li.offsetHeight) / Math.max(1, list.offsetHeight);
}

function go(anchor: string) {
  const el = document.getElementById(anchor);
  if (!el) return;
  active.value = anchor;
  scrollTo(el, { offset: -96 });
  history.replaceState(history.state, '', `#${encodeURIComponent(anchor)}`);
  emit('navigate', anchor);
}

watch(() => props.toc, () => requestAnimationFrame(setup));
watch(active, () => nextTick(place));

onMounted(() => {
  requestAnimationFrame(() => {
    setup();
    place();
    requestAnimationFrame(() => { ready.value = true; });
  });
  ro = new ResizeObserver(place);
  if (listRef.value) ro.observe(listRef.value);
});
onBeforeUnmount(() => {
  io?.disconnect();
  ro?.disconnect();
});

defineExpose({ go });
</script>

<template>
  <nav v-if="toc.length" class="toc" :class="{ 'is-ready': ready }" aria-label="文章目录">
    <p class="eyebrow toc-title">目录 · Contents</p>
    <div class="toc-body">
      <span class="toc-rail" aria-hidden="true">
        <span class="toc-fill" :style="{ transform: `scaleY(${fill.toFixed(4)})` }" />
      </span>
      <span
        class="toc-marker"
        :class="{ 'is-on': marker.on }"
        :style="{ transform: `translate3d(0, ${marker.y}px, 0)`, height: `${marker.h}px` }"
        aria-hidden="true"
      />
      <ol ref="listRef" class="toc-list">
        <li
          v-for="(item, i) in toc"
          :key="item.anchor"
          :class="[`lv-${item.level}`, { 'is-active': active === item.anchor, 'is-read': activeIndex > i }]"
        >
          <a :href="`#${item.anchor}`" :aria-current="active === item.anchor ? 'location' : undefined" @click.prevent="go(item.anchor)">
            <span class="toc-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="toc-text">{{ item.text }}</span>
          </a>
        </li>
      </ol>
    </div>
  </nav>
</template>

<style scoped>
.toc-title { margin-bottom: 14px; }
.toc-body { position: relative; }
.toc-rail {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--color-line);
  overflow: hidden;
}
.toc-fill {
  position: absolute;
  inset: 0;
  background: var(--color-line-strong);
  transform-origin: 50% 0;
}
.toc-marker {
  position: absolute;
  left: -1px;
  top: 0;
  width: 3px;
  border-radius: 2px;
  background: var(--color-accent);
  opacity: 0;
}
.toc-marker.is-on { opacity: 1; }
.toc.is-ready .toc-fill { transition: transform 700ms var(--ease-out-expo); }
.toc.is-ready .toc-marker {
  transition: transform 600ms var(--ease-spring), height 600ms var(--ease-spring), opacity 300ms ease;
}

.toc-list { list-style: none; }
.toc-list a {
  display: grid;
  grid-template-columns: 22px 1fr;
  align-items: baseline;
  gap: 6px;
  padding: 6px 0 6px 16px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-ink-muted);
  transition: color var(--dur-sm) var(--ease-out-quart), transform 500ms var(--ease-out-expo);
}
.toc-list a:hover { color: var(--color-ink); transform: translateX(2px); }
.toc-no {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--color-ink-faint);
  font-variant-numeric: tabular-nums;
  transition: color var(--dur-sm) ease;
}
.lv-3 .toc-text { padding-left: 10px; font-size: 12.5px; }
.is-read a { color: color-mix(in oklab, var(--color-ink) 50%, transparent); }
.is-active a { color: var(--color-ink); }
.is-active .toc-text { font-weight: 600; }
.is-active .toc-no { color: var(--color-accent); }
</style>
