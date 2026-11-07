<script setup lang="ts">
/** 开关：滑钮带弹簧缓动，按下时略微拉长（像真实的拨动开关） */
const props = defineProps<{ modelValue: boolean; label?: string; disabled?: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>();
</script>

<template>
  <button
    type="button"
    role="switch"
    class="a-switch"
    :class="{ 'is-on': props.modelValue }"
    :aria-checked="props.modelValue"
    :aria-label="label"
    :disabled="disabled"
    @click="emit('update:modelValue', !props.modelValue)"
  >
    <span class="a-switch-knob" />
  </button>
</template>

<style scoped>
.a-switch {
  position: relative;
  flex-shrink: 0;
  width: 36px;
  height: 20px;
  border-radius: 999px;
  background: var(--a-press);
  box-shadow: inset 0 0 0 1px var(--color-line-strong);
  transition: background-color var(--a-dur-md) var(--ease-out-quart), box-shadow var(--a-dur) ease;
}
.a-switch.is-on { background: var(--color-ink); box-shadow: inset 0 0 0 1px var(--color-ink); }
.a-switch[disabled] { opacity: 0.45; pointer-events: none; }
.a-switch-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  background: var(--a-paper);
  box-shadow: 0 1px 2px rgb(var(--shadow-rgb) / calc(0.3 * var(--shadow-k)));
  transition: transform var(--a-dur-md) var(--ease-spring), width var(--a-dur) var(--ease-out-quart);
}
.a-switch.is-on .a-switch-knob { transform: translateX(16px); }
.a-switch:active .a-switch-knob { width: 18px; }
.a-switch.is-on:active .a-switch-knob { transform: translateX(12px); }
</style>
