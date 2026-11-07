import { onMounted, onBeforeUnmount, type Ref } from 'vue';
import gsap from 'gsap';

/**
 * 凝字：标题从墨的扰动中沉淀成清晰的字（docs/design-v2.md §3）
 * 共用 <InkDefs> 里的 #ink-settle 滤镜：位移从 strength 推到 0、模糊从 6px 收到 0，结束后摘掉滤镜。
 * 页面挂载后开始；减弱动效、低档设备直接显示。
 */
export function useInkSettle(target: Ref<HTMLElement | null>, opts: { strength?: number; duration?: number; delay?: number } = {}) {
  let tl: gsap.core.Timeline | null = null;

  function play() {
    const el = target.value;
    const root = document.documentElement;
    const disp = document.querySelector('#ink-settle feDisplacementMap');
    const blur = document.querySelector('#ink-settle feGaussianBlur');
    if (!el || !disp || !blur || root.classList.contains('reduce-motion') || root.getAttribute('data-tier') === 'low') return;
    const strength = opts.strength ?? 70;
    el.classList.add('ink-settle');
    tl?.kill();
    tl = gsap.timeline({
      delay: opts.delay ?? 0,
      onComplete: () => el.classList.remove('ink-settle'),
    })
      .fromTo(disp, { attr: { scale: strength } }, { attr: { scale: 0 }, duration: opts.duration ?? 1.3, ease: 'outExpo' }, 0)
      .fromTo(blur, { attr: { stdDeviation: 6 } }, { attr: { stdDeviation: 0 }, duration: (opts.duration ?? 1.3) * 0.7, ease: 'outQuart' }, 0)
      .fromTo(el, { opacity: 0.25 }, { opacity: 1, duration: 0.6, ease: 'outQuart' }, 0);
  }

  onMounted(play);
  onBeforeUnmount(() => {
    tl?.kill();
    target.value?.classList.remove('ink-settle');
  });
  return { play };
}
