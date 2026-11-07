import { onMounted, type Ref } from 'vue';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import gsap from 'gsap';
import { DUR, STAGGER, sec, staggerFor } from './tokens';
import { useMotion } from '~/composables/useMotion';

/** 进入视口时逐个揭示子元素（只播一次）；动画在 gsap.context 内创建，卸载时自动 revert */
export function useSplitReveal(containerRef: Ref<HTMLElement | null>, selector = 'h1, h2, p') {
  const motion = useMotion();
  onMounted(() => {
    const root = containerRef.value;
    if (!root || motion.state.reduced) return;
    gsap.registerPlugin(ScrollTrigger);
    motion.ctx(root, () => {
      const items = root.querySelectorAll(selector);
      if (!items.length) return;
      gsap.from(items, {
        y: 24,
        opacity: 0,
        duration: sec(DUR.md),
        stagger: staggerFor(items.length, STAGGER.list),
        ease: 'outExpo',
        clearProps: 'transform,opacity',
        scrollTrigger: { trigger: root, start: 'top 85%', once: true },
      });
    });
  });
}
