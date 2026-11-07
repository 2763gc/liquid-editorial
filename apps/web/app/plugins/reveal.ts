import type { Directive } from 'vue';

/**
 * v-reveal：进入视口时出现，只播放一次（语汇：凝字——从墨的扰动中沉淀成形）。
 * 用法：<div v-reveal> 或 <div v-reveal="120">（延迟毫秒）
 * 标题逐行：<h1 v-reveal class="reveal-lines"><span class="line-mask"><span class="line-inner">…</span></span></h1>
 */
let observer: IntersectionObserver | null = null;

function getObserver(): IntersectionObserver | null {
  if (typeof window === 'undefined' || !('IntersectionObserver' in window)) return null;
  if (!observer) {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const el = entry.target;
          observer?.unobserve(el);
          el.classList.add('is-in');
        }
      },
      { rootMargin: '0px 0px -6% 0px', threshold: 0.06 },
    );
  }
  return observer;
}

const reveal: Directive<HTMLElement, number | undefined> = {
  getSSRProps() {
    return {};
  },
  mounted(el, binding) {
    if (!el.classList.contains('reveal-lines')) el.classList.add('reveal');
    if (binding.value) el.style.setProperty('--reveal-delay', `${Math.min(binding.value, 400)}ms`);
    el.querySelectorAll<HTMLElement>('.line-inner').forEach((line, i) => line.style.setProperty('--i', String(i)));
    const io = getObserver();
    if (!io || document.documentElement.classList.contains('reduce-motion')) {
      el.classList.add('is-in');
      return;
    }
    io.observe(el);
  },
  unmounted(el) {
    observer?.unobserve(el);
  },
};

export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.vueApp.directive('reveal', reveal);
});
