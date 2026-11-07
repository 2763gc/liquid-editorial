<script setup lang="ts">
/**
 * 全站共用的 SVG 滤镜定义（只渲染一次，放在布局里）
 * - ink-settle：凝字。湍流位移 + 模糊，强度由 useInkSettle 用 GSAP 从强推到零
 * - ink-bleed：洇。静态的轻微边缘扰动，用于悬停时的墨色洇开
 */
</script>

<template>
  <svg class="ink-defs" width="0" height="0" aria-hidden="true" focusable="false">
    <filter id="ink-settle" x="-10%" y="-30%" width="120%" height="160%" color-interpolation-filters="sRGB">
      <feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="3" seed="4" result="noise" />
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="0" xChannelSelector="R" yChannelSelector="G" result="moved" />
      <feGaussianBlur in="moved" stdDeviation="0" />
    </filter>
    <filter id="ink-bleed" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="2" result="n" />
      <feDisplacementMap in="SourceGraphic" in2="n" scale="1.6" xChannelSelector="R" yChannelSelector="G" />
    </filter>
  </svg>
</template>

<style scoped>
.ink-defs { position: absolute; width: 0; height: 0; overflow: hidden; pointer-events: none; }
</style>
