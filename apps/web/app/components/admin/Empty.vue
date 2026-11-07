<script setup lang="ts">
/** 空状态：一团淡墨里的图标 + 标题 + 提示 + 可选操作 */
defineProps<{ title: string; hint?: string }>();
</script>

<template>
  <div class="a-empty">
    <span class="a-empty-icon"><slot name="icon" /></span>
    <p class="a-empty-title">{{ title }}</p>
    <p v-if="hint" class="a-empty-hint">{{ hint }}</p>
    <div v-if="$slots.default" class="a-empty-actions"><slot /></div>
  </div>
</template>

<style scoped>
.a-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 24px;
  text-align: center;
}
.a-empty-icon {
  position: relative;
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  color: var(--color-ink-muted);
}
.a-empty-icon::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background: color-mix(in oklab, var(--color-ink) 7%, transparent);
  -webkit-mask-image: var(--ink-blot);
  mask-image: var(--ink-blot);
  -webkit-mask-size: 150% 150%;
  mask-size: 150% 150%;
  -webkit-mask-position: 50% 50%;
  mask-position: 50% 50%;
}
.a-empty-title { margin-top: 14px; font-family: var(--font-serif); font-size: 17px; font-weight: 700; }
.a-empty-hint { margin-top: 6px; max-width: 28em; font-size: 13px; line-height: 1.7; color: var(--color-ink-faint); }
.a-empty-actions { display: flex; gap: 8px; margin-top: 18px; }
</style>
