import { initTheme, useTheme } from '~/composables/useTheme';
import { onReducedChange } from '~/composables/useMotion';
import { watch } from 'vue';
import gsap from 'gsap';

/**
 * 四时光照 2.0 的运行时部分（任务书 §4.5）
 * - 水合完成后再初始化主题状态（避免 hydration 不一致；布局是异步组件，app:mounted 时还没水合完）
 * - 夜里把窗光换成「台灯」：光标附近一团极淡的暖光；只在高档桌面设备、只在正文以外的区域出现
 * - Favicon 随时段切换（P2）：同一枚朱砂方印，晨冷、暮暖、夜反白
 */
export default defineNuxtPlugin((nuxtApp) => {
  nuxtApp.hook('app:suspense:resolve', () => {
    if (useTheme().ready.value) return;
    initTheme();
    const theme = useTheme();
    const root = document.documentElement;

    /* ---- Favicon ---- */
    const icon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    const FILL: Record<string, [string, string]> = {
      morning: ['#EEF0F1', '#F04A2A'],
      day: ['#F2EFE8', '#FF4D2E'],
      dusk: ['#F3EBDF', '#F26A1B'],
      night: ['#0C0C0D', '#FF5A3C'],
    };
    const setIcon = () => {
      if (!icon) return;
      const [paper, ink] = FILL[theme.period.value] || FILL.day;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="3" fill="${paper}"/><rect x="7" y="7" width="18" height="18" fill="${ink}"/><path d="M12 11v10h8" stroke="${paper}" stroke-width="2.4" fill="none"/></svg>`;
      icon.href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
    };
    setIcon();
    watch(() => theme.period.value, setIcon);

    /* ---- 台灯 ---- */
    const fine = matchMedia('(hover: hover) and (pointer: fine)').matches;
    let lamp: HTMLElement | null = null;
    let off: (() => void) | null = null;
    const update = () => {
      const want = fine && root.getAttribute('data-tier') === 'high' && root.getAttribute('data-theme') === 'dark'
        && !root.classList.contains('reduce-motion') && !location.pathname.startsWith('/admin');
      if (want && !lamp) {
        lamp = document.createElement('div');
        lamp.className = 'desk-lamp';
        lamp.setAttribute('aria-hidden', 'true');
        document.body.appendChild(lamp);
        // 位置交给全站唯一的 ticker 写，指针事件只记录目标
        const setX = gsap.quickTo(lamp, 'x', { duration: 0.6, ease: 'outExpo' });
        const setY = gsap.quickTo(lamp, 'y', { duration: 0.6, ease: 'outExpo' });
        const onMove = (e: PointerEvent) => {
          setX(e.clientX);
          setY(e.clientY);
          const overProse = !!(e.target as Element | null)?.closest?.('.article-prose, .post-head, input, textarea');
          lamp?.classList.toggle('is-on', !overProse);
        };
        window.addEventListener('pointermove', onMove, { passive: true });
        off = () => {
          window.removeEventListener('pointermove', onMove);
          if (lamp) gsap.killTweensOf(lamp);
          lamp?.remove();
          lamp = null;
        };
      } else if (!want && lamp) {
        off?.();
      }
    };
    update();
    new MutationObserver(update).observe(root, { attributes: true, attributeFilter: ['data-theme', 'data-tier'] });
    onReducedChange(update);
    nuxtApp.hook('page:finish', update);
  });
});
