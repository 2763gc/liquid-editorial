import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { CustomEase } from 'gsap/CustomEase';
import { Flip } from 'gsap/Flip';
import { EASE, easePath, type EaseName } from '~/composables/motion/tokens';
import { initMotionState, onReducedChange, setTier, type Tier } from '~/composables/useMotion';
import { setLenisInstance } from '~/composables/useLenis';

/**
 * 动效基础设施（PRD 3.3 / 3.6 · 任务书 §4.3）
 * - 全站只有一个 rAF：gsap.ticker 同时驱动 Lenis、ScrollTrigger 和所有组件动画
 * - CustomEase 注册与 CSS 同名的缓动：outExpo、inOutQuart、outBack、impress、spring……
 * - Lenis 参数按设备档位微调；减弱动效时销毁 Lenis，回到原生滚动
 * - 页面不可见时 ticker 休眠
 * - 首屏后用 24 帧的实际耗时修正设备档位（中位数 > 22ms 降一档）
 */
export default defineNuxtPlugin((nuxtApp) => {
  gsap.registerPlugin(ScrollTrigger, CustomEase, Flip);
  for (const name of [...Object.keys(EASE), 'spring'] as EaseName[]) CustomEase.create(name, easePath(name));
  gsap.defaults({ ease: 'outExpo', duration: 0.7 });
  gsap.ticker.lagSmoothing(500, 33);

  initMotionState();
  const root = document.documentElement;
  const coarse = root.getAttribute('data-pointer') === 'coarse';

  let lenis: Lenis | null = null;
  const raf = (time: number) => lenis?.raf(time * 1000);

  function createLenis() {
    if (lenis || coarse || root.classList.contains('reduce-motion')) return;
    const tier = root.getAttribute('data-tier') as Tier;
    lenis = new Lenis({
      // 低档设备减少插值帧数，手感更跟手
      lerp: tier === 'low' ? 0.2 : tier === 'mid' ? 0.14 : 0.11,
      smoothWheel: true,
      wheelMultiplier: 1,
      // 浮层、代码块等内部滚动区域加 data-lenis-prevent 即可原生滚动
      prevent: (node: HTMLElement) => node.closest?.('[data-lenis-prevent]') !== null,
      // 锚点链接交给 Lenis，偏移避开粘性顶栏
      anchors: { offset: -88 },
    });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add(raf);
    setLenisInstance(lenis);
  }
  function destroyLenis() {
    if (!lenis) return;
    gsap.ticker.remove(raf);
    lenis.destroy();
    lenis = null;
    setLenisInstance(null);
  }
  createLenis();
  onReducedChange((reduced) => (reduced ? destroyLenis() : createLenis()));

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) gsap.ticker.sleep();
    else gsap.ticker.wake();
  });

  // 首帧耗时修正设备档位
  const samples: number[] = [];
  let last = 0;
  const probe = (time: number) => {
    if (last) samples.push((time - last) * 1000);
    last = time;
    if (samples.length < 24) return;
    gsap.ticker.remove(probe);
    const median = samples.sort((a, b) => a - b)[12];
    const tier = root.getAttribute('data-tier') as Tier;
    if (median > 22 && tier !== 'low') setTier(tier === 'high' ? 'mid' : 'low');
  };
  nuxtApp.hook('app:mounted', () => window.setTimeout(() => gsap.ticker.add(probe), 600));

  // 路由切换完成：重新测量内容高度与触发点
  nuxtApp.hook('page:finish', () => {
    gsap.ticker.add(function refresh() {
      gsap.ticker.remove(refresh);
      lenis?.resize();
      ScrollTrigger.refresh();
    });
  });

  // 字体加载完成后布局会变化，刷新一次触发点
  document.fonts?.ready.then(() => ScrollTrigger.refresh());

  if (import.meta.dev) Object.assign(window, { __gsap: gsap, __ScrollTrigger: ScrollTrigger });

  return { provide: { lenis: () => lenis } };
});
