<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import gsap from 'gsap';

/**
 * 点赞：钤一方朱砂「阅」印（docs/design-v2.md · M15）
 * 按下时印章带着轻微旋转从上方压下，回弹落定；印面有纸纹的不均匀感。
 * 计数像号码机一样滚动。乐观更新，失败时回滚并提示（B07）。
 */
const props = defineProps<{ slug: string; liked: boolean; count: number }>();
const emit = defineEmits<{ (e: 'announce', msg: string): void }>();

const isLiked = ref(props.liked);
const value = ref(props.count);
const busy = ref(false);
const sealRef = ref<HTMLElement | null>(null);
const failed = ref(false);
watch(() => [props.liked, props.count] as const, ([l, c]) => { isLiked.value = l; value.value = c; });

const digits = computed(() => String(value.value).padStart(3, '0').split(''));

async function stamp() {
  if (isLiked.value || busy.value) return;
  busy.value = true;
  failed.value = false;
  isLiked.value = true;
  value.value += 1;
  const seal = sealRef.value;
  if (seal && !document.documentElement.classList.contains('reduce-motion')) {
    gsap.fromTo(seal,
      { scale: 1.9, rotation: -14, opacity: 0, y: -18 },
      { scale: 1, rotation: -4, opacity: 1, y: 0, duration: 0.42, ease: 'outBack' });
    gsap.fromTo(seal.parentElement, { y: 0 }, { y: 2, duration: 0.08, yoyo: true, repeat: 1, delay: 0.18, ease: 'outQuart' });
  }
  try {
    const res = await $fetch<{ like_count: number; liked: boolean }>(`/api/v1/posts/${encodeURIComponent(props.slug)}/like`, { method: 'POST' });
    value.value = res.like_count;
    emit('announce', '已钤印，谢谢你的阅读');
  } catch {
    // 回滚：印章褪去
    isLiked.value = false;
    value.value = Math.max(0, value.value - 1);
    failed.value = true;
    if (seal) gsap.to(seal, { opacity: 0, scale: 1.2, duration: 0.3, ease: 'inQuart' });
    emit('announce', '印没有盖上，请稍后再试');
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <button type="button" class="like-seal" :class="{ 'is-liked': isLiked, 'is-failed': failed }" :aria-pressed="isLiked" :aria-label="isLiked ? `已阅，共 ${value} 人` : `钤印点赞，已有 ${value} 人`" @click="stamp">
    <span class="like-seal-pad" aria-hidden="true">
      <span class="like-seal-ghost">阅</span>
      <span ref="sealRef" class="like-seal-mark seal">阅</span>
    </span>
    <span class="like-seal-text">
      <span class="like-seal-label">{{ isLiked ? '已阅' : failed ? '未盖上 · 再试一次' : '钤印' }}</span>
      <span class="like-seal-count" aria-hidden="true">
        <span v-for="(d, i) in digits" :key="i" class="like-digit"><span :style="{ transform: `translateY(${-Number(d) * 10}%)` }">0123456789</span></span>
      </span>
    </span>
  </button>
</template>

<style scoped>
.like-seal {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  height: 64px;
  padding: 0 22px 0 10px;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-xs);
  transition: border-color var(--dur-sm) ease, background-color var(--dur-sm) ease, transform var(--dur-impress) var(--ease-impress);
}
.like-seal:hover { border-color: var(--color-ink); }
.like-seal:active { transform: scale(0.98); }
.like-seal-pad { position: relative; width: 46px; height: 46px; display: grid; place-items: center; }
.like-seal-ghost {
  position: absolute;
  inset: 4px;
  display: grid;
  place-items: center;
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 900;
  color: var(--color-ink-faint);
  border: 1px dashed var(--color-line-strong);
  border-radius: 3px;
  transition: opacity var(--dur-sm) ease;
}
.like-seal-mark {
  position: absolute;
  inset: 4px;
  width: auto;
  height: auto;
  font-size: 20px;
  color: var(--color-bg);
  background: var(--color-seal);
  border-color: var(--color-seal);
  opacity: 0;
  transform: rotate(-4deg);
}
.is-liked .like-seal-mark { opacity: 1; }
.is-liked .like-seal-ghost { opacity: 0; }
.like-seal-text { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
.like-seal-label { font-size: var(--fs-small); font-weight: 600; }
.is-failed .like-seal-label { color: var(--color-danger); }
.like-seal-count { display: inline-flex; font-family: var(--font-mono); font-size: 12px; color: var(--color-ink-muted); font-variant-numeric: tabular-nums; }
.like-digit { display: inline-block; height: 1.2em; overflow: hidden; line-height: 1.2; }
.like-digit > span {
  display: flex;
  flex-direction: column;
  word-break: break-all;
  width: 1ch;
  line-height: 1.2;
  transition: transform 700ms var(--ease-out-expo);
}
</style>
