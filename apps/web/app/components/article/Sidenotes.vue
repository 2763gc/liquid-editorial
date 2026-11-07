<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

/**
 * 页边旁注：宽屏下把脚注排进正文左侧的页边，与正文里的引用号对齐；
 * 悬停引用号或旁注时，一条发丝引线把两者连起来。窄屏保持文末脚注。
 * 只读几何、批量写入；正文尺寸变化（字体加载、阅读设置）时重新排。
 */
const props = defineProps<{ prose: HTMLElement | null }>();

interface Note { id: string; n: string; html: string; top: number }
const notes = ref<Note[]>([]);
const active = ref('');
const rootRef = ref<HTMLElement | null>(null);
const leader = ref({ x1: 0, y1: 0, x2: 0, y2: 0, on: false });
let ro: ResizeObserver | null = null;
let mq: MediaQueryList | null = null;

function layout() {
  const prose = props.prose;
  const root = rootRef.value;
  if (!prose || !root || !mq?.matches) {
    notes.value = [];
    prose?.classList.remove('has-sidenotes');
    return;
  }
  const base = root.getBoundingClientRect().top;
  const refs = Array.from(prose.querySelectorAll<HTMLAnchorElement>('.fn-ref a[data-fn]'));
  // 破栏进页边的代码 / 表格（图解版式）：旁注落在它们身上时挪到下方
  const left = prose.getBoundingClientRect().left;
  const blocks = Array.from(prose.children)
    .map((el) => el.getBoundingClientRect())
    .filter((r) => r.left < left - 1)
    .map((r) => [r.top - base - 16, r.bottom - base + 16] as const);
  const out: Note[] = [];
  let floor = 0;
  for (const a of refs) {
    const id = a.dataset.fn!;
    const li = prose.querySelector<HTMLElement>(`#fn${CSS.escape(id)}`);
    if (!li || out.some((o) => o.id === id)) continue;
    const clone = li.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('.footnote-backref').forEach((b) => b.remove());
    const height = Math.max(72, Math.ceil(clone.textContent!.length / 14) * 22 + 28);
    let top = Math.max(a.getBoundingClientRect().top - base - 4, floor);
    for (const [bt, bb] of blocks) if (top < bb && top + height - 28 > bt) top = bb;
    out.push({ id, n: a.textContent || id, html: clone.innerHTML, top });
    // 旁注之间至少留 3 行的距离，避免重叠
    floor = top + height;
  }
  notes.value = out;
  prose.classList.toggle('has-sidenotes', out.length > 0);
}

function link(id: string, on: boolean) {
  active.value = on ? id : '';
  const prose = props.prose;
  const root = rootRef.value;
  const a = prose?.querySelector<HTMLElement>(`.fn-ref a[data-fn="${CSS.escape(id)}"]`);
  prose?.querySelectorAll('.fn-ref a.is-linked').forEach((el) => el.classList.remove('is-linked'));
  if (!on || !a || !root) {
    leader.value = { ...leader.value, on: false };
    return;
  }
  a.classList.add('is-linked');
  const r = root.getBoundingClientRect();
  const ar = a.getBoundingClientRect();
  const note = root.querySelector<HTMLElement>(`[data-note="${CSS.escape(id)}"]`);
  const nr = note?.getBoundingClientRect();
  if (!nr) return;
  leader.value = { x1: nr.right - r.left + 8, y1: nr.top - r.top + 10, x2: ar.left - r.left - 4, y2: ar.top - r.top + ar.height / 2, on: true };
}

function onProseOver(e: Event) {
  const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('.fn-ref a[data-fn]');
  if (a) link(a.dataset.fn!, e.type === 'pointerover');
}

watch(() => props.prose, (el, old) => {
  old?.removeEventListener('pointerover', onProseOver);
  old?.removeEventListener('pointerout', onProseOver);
  if (!el) return;
  el.addEventListener('pointerover', onProseOver);
  el.addEventListener('pointerout', onProseOver);
  ro?.disconnect();
  ro = new ResizeObserver(layout);
  ro.observe(el);
  layout();
});

onMounted(() => {
  mq = window.matchMedia('(min-width: 1280px)');
  mq.addEventListener('change', layout);
  document.fonts?.ready.then(layout);
  if (props.prose) {
    props.prose.addEventListener('pointerover', onProseOver);
    props.prose.addEventListener('pointerout', onProseOver);
    ro = new ResizeObserver(layout);
    ro.observe(props.prose);
    layout();
  }
});
onBeforeUnmount(() => {
  ro?.disconnect();
  mq?.removeEventListener('change', layout);
  props.prose?.removeEventListener('pointerover', onProseOver);
  props.prose?.removeEventListener('pointerout', onProseOver);
});
</script>

<template>
  <div ref="rootRef" class="sidenotes" aria-hidden="true">
    <svg v-if="leader.on" class="sidenote-leader">
      <path :d="`M${leader.x1} ${leader.y1} H${(leader.x1 + leader.x2) / 2} V${leader.y2} H${leader.x2}`" />
    </svg>
    <aside
      v-for="note in notes"
      :key="note.id"
      class="sidenote"
      :class="{ 'is-active': active === note.id }"
      :data-note="note.id"
      :style="{ transform: `translate3d(0, ${note.top}px, 0)` }"
      @pointerenter="link(note.id, true)"
      @pointerleave="link(note.id, false)"
    >
      <span class="sidenote-n">{{ note.n }}</span>
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div class="sidenote-body" v-html="note.html" />
    </aside>
  </div>
</template>

<style scoped>
.sidenotes { position: relative; height: 100%; }
.sidenote {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 4px;
  font-family: var(--font-serif);
  font-size: 13px;
  line-height: 1.75;
  color: var(--color-ink-muted);
  transition: color var(--dur-sm) ease;
}
.sidenote.is-active { color: var(--color-ink); }
.sidenote-n {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 600;
  line-height: 2.2;
  color: var(--color-accent-text);
}
.sidenote-body :deep(p) { margin: 0; }
.sidenote-body :deep(a) { text-decoration: underline; text-underline-offset: 0.2em; text-decoration-color: var(--color-line-strong); }
.sidenote-leader {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}
.sidenote-leader path {
  fill: none;
  stroke: var(--color-accent);
  stroke-width: 1;
  stroke-dasharray: 600;
  stroke-dashoffset: 600;
  animation: leader-draw 520ms var(--ease-out-expo) forwards;
}
@keyframes leader-draw { to { stroke-dashoffset: 0; } }
</style>
