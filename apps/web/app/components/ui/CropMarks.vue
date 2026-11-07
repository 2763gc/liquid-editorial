<script setup lang="ts">
/**
 * 裁切与套准标记（任务书 §4.6）
 * - target：套准靶标（圆 + 十字），用于刊头、开场、加载态
 * - corners：四角裁切线，铺满父元素（父元素需 position: relative），用于刊头四角、图片角
 * 颜色跟随 currentColor；纯装饰，对读屏器隐藏。
 */
withDefaults(defineProps<{ variant?: 'target' | 'corners'; size?: number }>(), { variant: 'target', size: 14 });
</script>

<template>
  <svg v-if="variant === 'target'" class="crop-target" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <circle cx="12" cy="12" r="6.5" fill="none" stroke="currentColor" stroke-width="1" />
    <path d="M12 0v24M0 12h24" stroke="currentColor" stroke-width="1" />
    <circle cx="12" cy="12" r="2.2" fill="currentColor" />
  </svg>
  <span v-else class="crop-corners" :style="{ '--crop': `${size}px` }" aria-hidden="true">
    <i /><i /><i /><i />
  </span>
</template>

<style scoped>
.crop-target { display: inline-block; width: 1em; height: 1em; overflow: visible; }
.crop-corners {
  position: absolute;
  inset: calc(var(--crop) * -0.5);
  pointer-events: none;
}
.crop-corners i {
  position: absolute;
  width: var(--crop);
  height: var(--crop);
  border-color: currentColor;
  border-style: solid;
  border-width: 0;
}
.crop-corners i:nth-child(1) { left: 0; top: 0; border-left-width: 1px; border-top-width: 1px; }
.crop-corners i:nth-child(2) { right: 0; top: 0; border-right-width: 1px; border-top-width: 1px; }
.crop-corners i:nth-child(3) { left: 0; bottom: 0; border-left-width: 1px; border-bottom-width: 1px; }
.crop-corners i:nth-child(4) { right: 0; bottom: 0; border-right-width: 1px; border-bottom-width: 1px; }
</style>
