<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';

/**
 * 分段控件：选中态是一块会「滑」过去的墨色滑块（弹簧缓动），而不是瞬间换底色。
 * 滑块位置只写 transform / width，测量在挂载、选项变化与容器尺寸变化时进行。
 */
interface Option { value: string; label: string; count?: number }

const props = withDefaults(defineProps<{
  options: Option[];
  modelValue: string;
  ariaLabel?: string;
  size?: 'sm' | 'md';
  glass?: boolean;
}>(), { size: 'md', glass: false });

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const trackRef = ref<HTMLElement | null>(null);
const thumb = ref({ x: 0, w: 0 });
const ready = ref(false);
let ro: ResizeObserver | null = null;

function measure() {
  const track = trackRef.value;
  if (!track) return;
  const btn = track.querySelector<HTMLElement>(`[data-value="${CSS.escape(props.modelValue)}"]`);
  if (!btn) return;
  thumb.value = { x: btn.offsetLeft, w: btn.offsetWidth };
}

const thumbStyle = computed(() => ({
  transform: `translate3d(${thumb.value.x}px, 0, 0)`,
  width: `${thumb.value.w}px`,
}));

function select(v: string) {
  if (v !== props.modelValue) emit('update:modelValue', v);
}

function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
  e.preventDefault();
  const i = props.options.findIndex((o) => o.value === props.modelValue);
  const next = props.options[(i + (e.key === 'ArrowRight' ? 1 : -1) + props.options.length) % props.options.length];
  select(next.value);
  nextTick(() => trackRef.value?.querySelector<HTMLElement>(`[data-value="${CSS.escape(next.value)}"]`)?.focus());
}

watch(() => [props.modelValue, props.options.map((o) => `${o.value}:${o.count ?? ''}`).join('|')], () => nextTick(measure));

onMounted(() => {
  measure();
  // 首次定位不做动画，下一帧再打开过渡
  requestAnimationFrame(() => { ready.value = true; });
  ro = new ResizeObserver(measure);
  if (trackRef.value) ro.observe(trackRef.value);
  document.fonts?.ready.then(measure);
});
onBeforeUnmount(() => ro?.disconnect());
</script>

<template>
  <div
    ref="trackRef"
    class="seg"
    :class="[`seg-${size}`, { 'is-ready': ready, 'is-glass': glass }]"
    role="tablist"
    :aria-label="ariaLabel"
    @keydown="onKeydown"
  >
    <span class="seg-thumb" :style="thumbStyle" aria-hidden="true" />
    <button
      v-for="o in options"
      :key="o.value"
      type="button"
      role="tab"
      class="seg-btn"
      :class="{ 'is-active': o.value === modelValue }"
      :data-value="o.value"
      :aria-selected="o.value === modelValue"
      :tabindex="o.value === modelValue ? 0 : -1"
      @click="select(o.value)"
    >
      {{ o.label }}<sup v-if="o.count != null" class="seg-count">{{ o.count }}</sup>
    </button>
  </div>
</template>

<style scoped>
.seg {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-pill);
  isolation: isolate;
}
.seg.is-glass {
  background: color-mix(in oklab, var(--color-bg) 82%, transparent);
  box-shadow: var(--shadow-md), var(--edge-light);
  -webkit-backdrop-filter: blur(14px) saturate(1.5);
  backdrop-filter: blur(14px) saturate(1.5);
}
.seg-thumb {
  position: absolute;
  top: 3px;
  bottom: 3px;
  left: 0;
  z-index: -1;
  border-radius: var(--radius-pill);
  background: var(--color-ink);
  box-shadow: 0 1px 2px rgb(var(--shadow-rgb) / 0.2), inset 0 1px 0 rgb(255 255 255 / 0.12);
  will-change: transform;
}
.seg.is-ready .seg-thumb {
  transition: transform 560ms var(--ease-spring), width 560ms var(--ease-spring);
}
.seg-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 14px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-micro);
  font-weight: 500;
  white-space: nowrap;
  color: var(--color-ink-muted);
  transition: color 320ms var(--ease-out-quart);
}
.seg-btn:hover { color: var(--color-ink); }
.seg-btn.is-active { color: var(--color-bg); }
.seg-btn:focus-visible { outline-offset: 1px; }
.seg-count {
  font-family: var(--font-mono);
  font-size: 9.5px;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
}
.seg-sm .seg-btn { height: 26px; padding: 0 11px; font-size: 11.5px; }
</style>
