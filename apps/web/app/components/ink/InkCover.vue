<script setup lang="ts">
import { computed, useId } from 'vue';
import { inkArt, type InkVariant } from '~/utils/inkArt';
import { pigmentFor } from '~/utils/pigment';

/**
 * 水墨封面：按 slug 生成的一幅水墨（远山 / 墨晕 / 皴笔 / 折枝 / 孤月）+ 期号大字 + 朱砂印。
 * 服务端直接输出内联 SVG，颜色全部取自 Token，四时光照与明暗切换时跟着变。
 */
const props = withDefaults(defineProps<{
  seed: string;
  no?: number | null;
  accent?: string | null;
  variant?: InkVariant;
  width?: number;
  height?: number;
  /** 是否显示大号期号（列表缩略图里可关闭） */
  numeral?: boolean;
  seal?: boolean;
  /** 墨的浓度倍数：整屏头图需要更重的墨 */
  intensity?: number;
  /** 不画纸底：直接晕在页面上 */
  bare?: boolean;
}>(), { width: 400, height: 250, numeral: true, seal: true, intensity: 1, bare: false });

const uid = useId();
const art = computed(() => inkArt(props.seed, props.width, props.height, props.variant));
const no = computed(() => String(props.no ?? 0).padStart(3, '0'));
/** 设色：文章强调色就近映射为传统颜料；印章始终朱砂 */
const style = computed(() => {
  const p = pigmentFor(props.accent);
  return { '--cover-pigment': p.color, '--cover-pigment-night': p.night };
});
const wet = `w${uid}`.replace(/[^a-zA-Z0-9_-]/g, '');
/** 湍流频率按画幅换算：同一幅画放大后纹理跟着放大，不会变成细碎的马赛克 */
const k = computed(() => 400 / props.width);
const wetFreq = computed(() => (0.012 * k.value).toFixed(5));
const dryFreq = computed(() => `${(0.012 * k.value).toFixed(5)} ${(0.16 * k.value).toFixed(5)}`);
const tone = (t: number) => Math.min(1, t * props.intensity);
const dry = `d${uid}`.replace(/[^a-zA-Z0-9_-]/g, '');
const soft = `s${uid}`.replace(/[^a-zA-Z0-9_-]/g, '');
const filterId = (f: string) => (f === 'wet' ? wet : f === 'dry' ? dry : soft);
</script>

<template>
  <svg
    class="ink-cover"
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="xMidYMid slice"
    :style="style"
    aria-hidden="true"
    focusable="false"
  >
    <defs>
      <!-- 湿墨：低频湍流推开边缘，再轻微模糊 -->
      <filter :id="wet" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" :baseFrequency="wetFreq" numOctaves="4" :seed="art.seed % 997" />
        <feDisplacementMap in="SourceGraphic" :scale="width / 18" xChannelSelector="R" yChannelSelector="G" />
        <feGaussianBlur :stdDeviation="width / 260" />
      </filter>
      <!-- 枯笔：沿笔势方向拉长的湍流把笔画撕出飞白，边缘再轻轻柔化 -->
      <filter :id="dry" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" :baseFrequency="dryFreq" numOctaves="3" :seed="(art.seed % 991) + 3" result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" :scale="width / 70" xChannelSelector="R" yChannelSelector="G" result="d" />
        <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 2.6 -0.75" result="mask" />
        <feComposite in="d" in2="mask" operator="in" result="c" />
        <feGaussianBlur in="c" :stdDeviation="width / 900" />
      </filter>
      <!-- 柔边：极小的位移只让边缘有手作感，形状不走样 -->
      <filter :id="soft" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" :baseFrequency="wetFreq" numOctaves="2" :seed="(art.seed % 983) + 7" />
        <feDisplacementMap in="SourceGraphic" :scale="width / 160" xChannelSelector="R" yChannelSelector="G" />
        <feGaussianBlur :stdDeviation="width / 400" />
      </filter>
    </defs>

    <rect v-if="!bare" class="ink-cover-paper" :width="width" :height="height" />

    <g v-for="(s, i) in art.shapes" :key="i" :filter="`url(#${filterId(s.filter)})`" :class="{ 'is-accent': s.accent }">
      <path v-if="s.d && s.kind === 'fill'" :d="s.d" class="ink-cover-fill" :style="{ opacity: tone(s.tone) }" />
      <path v-else-if="s.d" :d="s.d" class="ink-cover-stroke" :stroke-width="s.width" :style="{ opacity: tone(s.tone) }" />
      <circle v-else-if="s.kind === 'ring'" :cx="s.cx" :cy="s.cy" :r="s.r" class="ink-cover-ring" :stroke-width="s.width" :style="{ opacity: tone(s.tone) }" />
      <circle v-else :cx="s.cx" :cy="s.cy" :r="s.r" class="ink-cover-fill" :style="{ opacity: tone(s.tone) }" />
    </g>

    <text v-if="numeral" class="ink-cover-no" :x="width * 0.045" :y="height * 0.94" :font-size="height * 0.5">{{ no }}</text>

    <g v-if="seal" class="ink-cover-seal" :transform="`translate(${art.seal.x} ${art.seal.y}) rotate(${art.seal.rot})`">
      <rect x="-15" y="-15" width="30" height="30" rx="2.5" />
      <text x="0" y="1" text-anchor="middle" dominant-baseline="middle">{{ no }}</text>
    </g>
  </svg>
</template>

<style scoped>
.ink-cover { display: block; width: 100%; height: 100%; }
.ink-cover-paper { fill: var(--color-surface); }
.ink-cover-fill { fill: var(--color-ink); }
.ink-cover-stroke,
.ink-cover-ring { fill: none; stroke: var(--color-ink); stroke-linecap: round; }
.is-accent .ink-cover-fill { fill: var(--cover-pigment, var(--color-accent)); }
:global(html[data-theme="dark"]) .is-accent .ink-cover-fill { fill: var(--cover-pigment-night, var(--color-accent)); }
.ink-cover-no {
  font-family: var(--font-display);
  font-style: italic;
  font-weight: 300;
  letter-spacing: -0.06em;
  fill: none;
  stroke: var(--color-ink);
  stroke-width: 0.8;
  opacity: 0.32;
  font-variation-settings: "opsz" 144, "SOFT" 100;
}
.ink-cover-seal rect { fill: var(--color-accent); }
.ink-cover-seal text {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: -0.02em;
  fill: var(--color-bg);
}
</style>
