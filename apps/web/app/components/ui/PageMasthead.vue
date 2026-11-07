<script setup lang="ts">
import { ref } from 'vue';
import { useInkSettle } from '~/composables/motion/useInkSettle';

/**
 * 栏目刊头：所有栏目页共用的开篇版式
 * 眉题（§ 序号 · 英文栏目名 · 中文标签）→ 大标题 → 导语 → 数据行 → 附加控件
 * 序号与全屏菜单中的编号一致，右上角以浅色斜体大字重复一次；大字背后晕着一团按栏目名生成的墨，
 * 每个栏目都有自己的墨迹。标题从墨的扰动中凝出（凝字）。
 */
const titleRef = ref<HTMLElement | null>(null);
useInkSettle(titleRef, { strength: 60, duration: 1.3 });

defineProps<{
  index?: string;
  en: string;
  label?: string;
  title: string;
  lede?: string;
  stats?: Array<{ label: string; value: string | number; unit?: string }>;
  /** md：标题是一句完整的话时使用较小字号 */
  size?: 'lg' | 'md';
}>();
</script>

<template>
  <header class="masthead page-shell" :class="`is-${size || 'lg'}`">
    <span class="masthead-ink" aria-hidden="true"><InkCover :seed="en + (index || '')" variant="bloom" :width="520" :height="420" :numeral="false" :seal="false" bare /></span>
    <span v-if="index" class="masthead-numeral font-display" aria-hidden="true">{{ index }}</span>

    <div v-reveal class="masthead-kicker reveal">
      <span v-if="index" class="masthead-index">§ {{ index }}</span>
      <span class="masthead-en">{{ en }}</span>
      <span class="masthead-rule" aria-hidden="true" />
      <span v-if="label" class="masthead-label">{{ label }}</span>
      <slot name="kicker" />
    </div>

    <h1 ref="titleRef" class="masthead-title"><slot name="title">{{ title }}</slot></h1>

    <p v-if="lede" v-reveal="180" class="masthead-lede reveal">{{ lede }}</p>

    <dl v-if="stats?.length" v-reveal="260" class="masthead-stats reveal">
      <div v-for="s in stats" :key="s.label" class="masthead-stat">
        <dt>{{ s.label }}</dt>
        <dd><span class="masthead-stat-value">{{ s.value }}</span><small v-if="s.unit">{{ s.unit }}</small></dd>
      </div>
    </dl>

    <div v-if="$slots.default" v-reveal="320" class="masthead-extra reveal">
      <slot />
    </div>
  </header>
</template>

<style scoped>
.masthead {
  position: relative;
  padding-block: clamp(56px, 8.5vw, 132px) clamp(28px, 3.6vw, 48px);
}
/* 刊头底部的墨线：进入页面时由左至右绘出 */
.masthead::after {
  content: "";
  position: absolute;
  left: var(--page-padding);
  right: var(--page-padding);
  bottom: 0;
  height: 1px;
  background: var(--color-ink);
  transform-origin: 0 50%;
  animation: masthead-rule 1400ms var(--ease-out-expo) 120ms both;
}
@keyframes masthead-rule { from { transform: scaleX(0); } }
html.reduce-motion .masthead::after { animation: none; }

.masthead-ink {
  position: absolute;
  top: clamp(-20px, -1vw, 0px);
  right: calc(var(--page-padding) - 40px);
  width: clamp(240px, 36vw, 520px);
  aspect-ratio: 520 / 420;
  opacity: 0.55;
  pointer-events: none;
  animation: masthead-ink 2200ms var(--ease-out-expo) both;
}
@keyframes masthead-ink { from { opacity: 0; transform: scale(0.86); filter: blur(12px); } }
html.reduce-motion .masthead-ink { animation: none; }
.masthead-numeral {
  position: absolute;
  top: clamp(20px, 3.5vw, 56px);
  right: var(--page-padding);
  font-size: clamp(120px, 19vw, 300px);
  font-style: italic;
  font-weight: 300;
  line-height: 0.8;
  letter-spacing: -0.06em;
  color: color-mix(in oklab, var(--color-ink) 9%, transparent);
  font-variation-settings: "opsz" 144, "SOFT" 100, "WONK" 1;
  pointer-events: none;
  user-select: none;
  animation: masthead-numeral 1600ms var(--ease-out-expo) both;
}
@keyframes masthead-numeral {
  from { opacity: 0; transform: translate3d(0, 6%, 0); }
}
html.reduce-motion .masthead-numeral { animation: none; }

.masthead-kicker {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.masthead-index { color: var(--color-accent-text); }
.masthead-rule { width: 44px; height: 1px; background: var(--color-line-strong); }
.masthead-label { font-family: var(--font-sans); letter-spacing: 0.14em; }

.masthead-title {
  position: relative;
  max-width: 14em;
  margin-top: clamp(20px, 2.4vw, 32px);
  font-family: var(--font-serif);
  font-size: clamp(44px, 7.4vw, 116px);
  font-weight: 900;
  line-height: 1.04;
  letter-spacing: -0.035em;
}

.is-md .masthead-title {
  max-width: 17em;
  font-size: clamp(36px, 5.2vw, 80px);
  line-height: 1.14;
  letter-spacing: -0.03em;
}

.masthead-lede {
  position: relative;
  max-width: 34em;
  margin-top: clamp(18px, 2vw, 26px);
  font-family: var(--font-serif);
  font-size: clamp(16.5px, 1.35vw, 19.5px);
  line-height: 1.85;
  color: var(--color-ink-muted);
}

.masthead-stats {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 16px clamp(28px, 4vw, 64px);
  margin-top: clamp(28px, 3.4vw, 44px);
}
.masthead-stat { display: flex; flex-direction: column; gap: 6px; }
.masthead-stat dt {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-faint);
}
.masthead-stat dd { display: flex; align-items: baseline; gap: 4px; }
.masthead-stat-value {
  font-family: var(--font-display);
  font-size: clamp(26px, 2.6vw, 36px);
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums lining-nums;
  font-variation-settings: "opsz" 72, "SOFT" 50;
}
.masthead-stat dd small { font-size: 12px; color: var(--color-ink-muted); }

.masthead-extra { position: relative; margin-top: clamp(28px, 3.2vw, 40px); }

@media (max-width: 640px) {
  .masthead-numeral { font-size: 34vw; top: 28px; }
  .masthead-rule { width: 24px; }
}
</style>
