<script setup lang="ts">
import { X } from 'lucide-vue-next';
import { useToast } from '~/composables/admin/useToast';

const { toasts, dismiss } = useToast();
/** 印文：成（完成）· 误（出错）· 注（提示） */
const SEAL = { success: '成', error: '误', info: '注' } as const;
</script>

<template>
  <Teleport to="body">
    <div class="a-toaster" role="region" aria-label="通知" aria-live="polite">
      <TransitionGroup name="a-toast">
        <div v-for="t in toasts" :key="t.id" class="a-toast" :class="`is-${t.kind}`" role="status">
          <span class="a-toast-seal" aria-hidden="true">{{ SEAL[t.kind] }}</span>
          <div class="a-toast-text">
            <p class="a-toast-title">{{ t.title }}</p>
            <p v-if="t.detail" class="a-toast-detail">{{ t.detail }}</p>
          </div>
          <button type="button" class="a-toast-close" aria-label="关闭通知" @click="dismiss(t.id)"><X :size="14" /></button>
          <span class="a-toast-timer" :style="{ animationDuration: `${t.duration}ms` }" @animationend="dismiss(t.id)" />
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.a-toaster {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1300;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  pointer-events: none;
}
.a-toast {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: start;
  gap: 12px;
  width: min(360px, calc(100vw - 40px));
  padding: 12px 10px 13px 12px;
  overflow: hidden;
  color: var(--color-ink);
  background: var(--a-paper);
  border: 1px solid var(--color-line-strong);
  border-radius: var(--a-radius);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
}
/* 小印：钤下时略微旋转、回弹落定 */
.a-toast-seal {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin-top: 1px;
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 900;
  color: var(--day-bg);
  border-radius: 2px;
  background: var(--color-ink-muted);
  transform: rotate(-4deg);
  animation: a-seal 360ms var(--ease-out-back) backwards 80ms;
}
.is-success .a-toast-seal { background: var(--a-ok); }
.is-error .a-toast-seal { background: var(--color-seal); }
.is-info .a-toast-seal { background: var(--color-ink); }
@keyframes a-seal { from { transform: scale(1.7) rotate(-14deg); opacity: 0; } }
html.reduce-motion .a-toast-seal { animation: none; }
.a-toast-title { font-size: 13.5px; font-weight: 600; line-height: 1.5; }
.a-toast-detail { margin-top: 2px; font-size: 12.5px; line-height: 1.6; color: var(--color-ink-muted); overflow-wrap: anywhere; }
.a-toast-close {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  margin: -2px -2px 0 0;
  border-radius: var(--a-radius-sm);
  color: var(--color-ink-faint);
  transition: color var(--a-dur) ease, background-color var(--a-dur) ease;
}
.a-toast-close:hover { color: var(--color-ink); background: var(--a-hover); }
/* 底部倒计时墨线；悬停时暂停，提示随之停留 */
.a-toast-timer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: var(--color-ink);
  opacity: 0.5;
  transform-origin: 0 50%;
  animation: a-toast-timer linear forwards;
}
.is-error .a-toast-timer { background: var(--color-seal); }
.a-toast:hover .a-toast-timer { animation-play-state: paused; }
@keyframes a-toast-timer { from { transform: scaleX(1); } to { transform: scaleX(0); } }

.a-toast-enter-active { transition: transform var(--a-dur-lg) var(--ease-out-expo), opacity var(--a-dur) ease; }
.a-toast-leave-active { transition: transform var(--a-dur) var(--ease-in-quart), opacity var(--a-dur) ease; }
.a-toast-enter-from { opacity: 0; transform: translate3d(0, 12px, 0); }
.a-toast-leave-to { opacity: 0; transform: translate3d(16px, 0, 0); }
.a-toast-move { transition: transform var(--a-dur-md) var(--ease-out-expo); }
</style>
