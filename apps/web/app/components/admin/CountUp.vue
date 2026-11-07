<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
import gsap from 'gsap';

/**
 * 数字从上一次的值滚动到新值（outExpo）；交给全站唯一的 gsap.ticker，不另开 rAF。
 * 后台动效减半：默认 0.6 秒。动效减弱时直接显示。
 */
const props = withDefaults(defineProps<{ value: number; duration?: number; format?: (n: number) => string }>(), { duration: 0.6 });
const shown = ref(0);
const state = { v: 0 };
let tween: gsap.core.Tween | null = null;

function run(to: number) {
  tween?.kill();
  if (document.documentElement.classList.contains('reduce-motion') || state.v === to) {
    state.v = to;
    shown.value = to;
    return;
  }
  tween = gsap.to(state, { v: to, duration: props.duration, ease: 'outExpo', onUpdate: () => { shown.value = state.v; } });
}

watch(() => props.value, (v) => run(v));
onMounted(() => run(props.value));
onBeforeUnmount(() => tween?.kill());
</script>

<template>
  <span class="a-count">{{ format ? format(Math.round(shown)) : Math.round(shown).toLocaleString('zh-CN') }}</span>
</template>

<style scoped>
.a-count { font-variant-numeric: tabular-nums lining-nums; }
</style>
