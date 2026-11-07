<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { useConfirm } from '~/composables/admin/useConfirm';

const { state, settle } = useConfirm();
const okRef = ref<HTMLButtonElement | null>(null);
let lastFocus: HTMLElement | null = null;

watch(() => state.open, (open) => {
  if (open) {
    lastFocus = document.activeElement as HTMLElement | null;
    nextTick(() => okRef.value?.focus());
  } else {
    lastFocus?.focus?.();
  }
});

function onKey(e: KeyboardEvent) {
  if (!state.open) return;
  if (e.key === 'Escape') settle(false);
}
onMounted(() => window.addEventListener('keydown', onKey));
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <Teleport to="body">
    <Transition name="a-modal">
      <div v-if="state.open" class="a-modal-backdrop" @mousedown.self="settle(false)">
        <div class="a-modal" role="alertdialog" aria-modal="true" :aria-label="state.opts.title">
          <span class="a-modal-seal" :class="{ 'is-danger': state.opts.danger }" aria-hidden="true">{{ state.opts.danger ? '删' : '问' }}</span>
          <h2 class="a-modal-title">{{ state.opts.title }}</h2>
          <p v-if="state.opts.message" class="a-modal-msg">{{ state.opts.message }}</p>
          <div class="a-modal-actions">
            <button type="button" class="a-btn" @click="settle(false)">{{ state.opts.cancelText || '取消' }}</button>
            <button
              ref="okRef"
              type="button"
              class="a-btn"
              :class="state.opts.danger ? 'a-btn-danger-solid' : 'a-btn-primary'"
              @click="settle(true)"
            >{{ state.opts.confirmText || '确定' }}</button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.a-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1250;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in oklab, var(--a-desk) 55%, transparent);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}
.a-modal {
  position: relative;
  width: min(420px, 100%);
  padding: 22px 24px 20px;
  color: var(--color-ink);
  background: var(--a-paper);
  border: 1px solid var(--color-line-strong);
  border-top: 2px solid var(--color-ink);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-float);
}
.a-modal-seal {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 900;
  color: var(--day-bg);
  background: var(--color-ink);
  border-radius: 3px;
  transform: rotate(-4deg);
}
.a-modal-seal.is-danger { background: var(--color-seal); }
.a-modal-title { margin-top: 14px; font-family: var(--font-serif); font-size: 19px; font-weight: 700; line-height: 1.4; }
.a-modal-msg { margin-top: 8px; font-size: 13.5px; line-height: 1.75; color: var(--color-ink-muted); }
.a-modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 22px; padding-top: 16px; border-top: 1px solid var(--color-line); }

.a-modal-enter-active { transition: opacity var(--a-dur) ease; }
.a-modal-enter-active .a-modal { transition: transform var(--a-dur-md) var(--ease-out-expo), opacity var(--a-dur) ease; }
.a-modal-leave-active { transition: opacity 120ms ease; }
.a-modal-leave-active .a-modal { transition: transform 120ms var(--ease-in-quart), opacity 120ms ease; }
.a-modal-enter-from, .a-modal-leave-to { opacity: 0; }
.a-modal-enter-from .a-modal { opacity: 0; transform: translate3d(0, 8px, 0) scale(0.98); }
.a-modal-leave-to .a-modal { opacity: 0; transform: scale(0.99); }
</style>
