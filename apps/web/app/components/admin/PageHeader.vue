<script setup lang="ts">
/** 后台页头：编号眉题 + 衬线标题 + 说明，右侧放主要操作 */
defineProps<{ index?: string; en: string; title: string; description?: string }>();
</script>

<template>
  <header class="a-head a-rise">
    <div class="a-head-text">
      <p class="a-head-eyebrow"><span v-if="index">§ {{ index }}</span>{{ en }}</p>
      <h1 class="a-head-title">{{ title }}</h1>
      <p v-if="description || $slots.description" class="a-head-desc"><slot name="description">{{ description }}</slot></p>
    </div>
    <div v-if="$slots.default" class="a-head-actions"><slot /></div>
  </header>
</template>

<style scoped>
.a-head {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px 24px;
  padding-bottom: 20px;
  margin-bottom: 26px;
}
/* 页头下沿的墨线：进入页面时由左至右绘出 */
.a-head::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: var(--color-ink);
  transform-origin: 0 50%;
  animation: a-head-rule var(--a-dur-lg) var(--ease-out-expo) both 60ms;
}
@keyframes a-head-rule { from { transform: scaleX(0); } }
html.reduce-motion .a-head::after { animation: none; }
.a-head-eyebrow {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-faint);
}
.a-head-eyebrow span { color: var(--color-accent-text); }
.a-head-eyebrow span::after { content: ""; display: inline-block; width: 20px; height: 1px; margin-left: 10px; vertical-align: middle; background: var(--color-line-strong); }
.a-head-title {
  margin-top: 10px;
  font-family: var(--font-serif);
  font-size: clamp(26px, 2.6vw, 36px);
  font-weight: 900;
  line-height: 1.15;
  letter-spacing: -0.02em;
}
.a-head-desc { margin-top: 8px; font-size: 13.5px; line-height: 1.7; color: var(--color-ink-muted); }
.a-head-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
</style>
