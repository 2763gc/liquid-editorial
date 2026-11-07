import gsap from 'gsap';
import { MOTION, frameLerp } from '~/composables/motion/tokens';
import { useLenis } from '~/composables/useLenis';

/**
 * M8 速度形变（任务书 §4.8）
 * 列表与图片容器（带 data-skew）随滚动速度做 skewY，最大 ±2°；停下后用弹簧回正。
 * - 只写可见元素的 transform（IntersectionObserver 维护集合）
 * - 形变期间挂 will-change 提升为合成层，skew 交给 GPU；否则每帧都要把整张列表连同文字重新栅格化（实测掉帧 ~10%）。
 *   回正后摘掉，静止时文字照常栅格，不常驻图层
 * - 速度来自 Lenis；原生滚动时由相邻两帧的 scrollY 差估算
 * - 正文（.article-prose）内部永远不形变；减弱动效与低档设备关闭
 */
export default defineNuxtPlugin((nuxtApp) => {
  const root = document.documentElement;
  const visible = new Set<HTMLElement>();
  let io: IntersectionObserver | null = null;
  let skew = 0;
  let vel = 0;
  let lastY = window.scrollY;
  let resting = true;

  function collect() {
    io?.disconnect();
    visible.clear();
    io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const el = e.target as HTMLElement;
        if (e.isIntersecting) visible.add(el);
        else {
          visible.delete(el);
          el.style.transform = '';
          el.style.willChange = '';
        }
      }
    });
    document.querySelectorAll<HTMLElement>('[data-skew]').forEach((el) => {
      if (!el.closest('.article-prose')) io!.observe(el);
    });
  }

  function enabled() {
    return !root.classList.contains('reduce-motion') && root.getAttribute('data-tier') !== 'low';
  }

  gsap.ticker.add((_t, deltaMs) => {
    if (!visible.size) return;
    const lenis = useLenis().getLenis();
    const y = window.scrollY;
    const raw = lenis ? lenis.velocity : (y - lastY) / Math.max(1, deltaMs / 16.667);
    lastY = y;
    vel += (raw - vel) * frameLerp(0.2, deltaMs);
    const target = enabled() ? Math.max(-MOTION.skewMax, Math.min(MOTION.skewMax, vel * 0.08)) : 0;
    // 弹簧式回正：靠近 0 时收得更慢，落定前不会突然停住
    skew += (target - skew) * frameLerp(target === 0 ? 0.08 : 0.14, deltaMs);
    if (Math.abs(skew) < 0.002 && Math.abs(target) < 0.002) {
      if (resting) return;
      skew = 0;
      resting = true;
      visible.forEach((el) => {
        el.style.transform = '';
        el.style.willChange = '';
      });
      return;
    }
    resting = false;
    const value = `skewY(${skew.toFixed(3)}deg)`;
    visible.forEach((el) => {
      el.style.willChange = 'transform';
      el.style.transform = value;
    });
  });

  nuxtApp.hook('page:finish', () => gsap.delayedCall(0.05, collect));
  nuxtApp.hook('app:mounted', collect);
});
