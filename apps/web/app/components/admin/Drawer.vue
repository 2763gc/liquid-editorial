<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue';
import { X } from 'lucide-vue-next';
import { lockScroll, unlockScroll } from '~/composables/useLenis';

/** 右侧滑出的表单面板：弹簧滑入、Esc / 点遮罩关闭、打开时聚焦第一个输入框 */
const props = withDefaults(defineProps<{ open: boolean; title: string; subtitle?: string; width?: number }>(), { width: 520 });
const emit = defineEmits<{ (e: 'close'): void }>();

const panelRef = ref<HTMLElement | null>(null);
let locked = false;

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close');
}

watch(() => props.open, (open) => {
  if (open) {
    if (!locked) { lockScroll(); locked = true; }
    window.addEventListener('keydown', onKey);
    nextTick(() => panelRef.value?.querySelector<HTMLElement>('input, textarea, select')?.focus({ preventScroll: true }));
  } else {
    if (locked) { unlockScroll(); locked = false; }
    window.removeEventListener('keydown', onKey);
  }
}, { immediate: true });

onBeforeUnmount(() => {
  if (locked) unlockScroll();
  window.removeEventListener('keydown', onKey);
});
</script>

<template>
  <Teleport to="body">
    <Transition name="a-drawer">
      <div v-if="open" class="a-drawer-backdrop" @mousedown.self="emit('close')">
        <aside
          ref="panelRef"
          class="a-drawer"
          role="dialog"
          aria-modal="true"
          :aria-label="title"
          :style="{ width: `min(${width}px, 100vw)` }"
          data-lenis-prevent
        >
          <header class="a-drawer-head">
            <div>
              <h2 class="a-drawer-title">{{ title }}</h2>
              <p v-if="subtitle" class="a-drawer-sub">{{ subtitle }}</p>
            </div>
            <button type="button" class="a-icon-btn" aria-label="关闭" @click="emit('close')"><X :size="17" /></button>
          </header>
          <div class="a-drawer-body"><slot /></div>
          <footer v-if="$slots.footer" class="a-drawer-foot"><slot name="footer" /></footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.a-drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  justify-content: flex-end;
  background: color-mix(in oklab, var(--a-desk) 45%, transparent);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}
.a-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  color: var(--color-ink);
  background: var(--a-paper);
  border-left: 1px solid var(--color-line-strong);
  box-shadow: -24px 0 60px -30px rgb(var(--shadow-rgb) / calc(0.35 * var(--shadow-k)));
}
.a-drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 20px 16px 24px;
  border-bottom: 1px solid var(--color-ink);
}
.a-drawer-title { font-family: var(--font-serif); font-size: 19px; font-weight: 700; line-height: 1.35; }
.a-drawer-sub { margin-top: 3px; font-size: 12.5px; color: var(--color-ink-faint); }
.a-drawer-body {
  flex: 1;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 22px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.a-drawer-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px;
  border-top: 1px solid var(--color-line);
  background: var(--a-desk);
}
.a-drawer-enter-active { transition: opacity var(--a-dur) ease; }
.a-drawer-enter-active .a-drawer { transition: transform var(--a-dur-lg) var(--ease-out-expo); }
.a-drawer-leave-active { transition: opacity var(--a-dur) ease 40ms; }
.a-drawer-leave-active .a-drawer { transition: transform var(--a-dur) var(--ease-in-quart); }
.a-drawer-enter-from, .a-drawer-leave-to { opacity: 0; }
.a-drawer-enter-from .a-drawer, .a-drawer-leave-to .a-drawer { transform: translate3d(100%, 0, 0); }
</style>
