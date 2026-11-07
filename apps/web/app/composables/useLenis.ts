import type Lenis from 'lenis';

/** 全站唯一的 Lenis 实例由 plugins/motion.client.ts 创建，这里只提供访问方法。 */
let instance: Lenis | null = null;

export function setLenisInstance(lenis: Lenis | null) {
  instance = lenis;
}

type ScrollTarget = string | number | HTMLElement;
interface ScrollOptions {
  offset?: number;
  duration?: number;
  immediate?: boolean;
  force?: boolean;
  lock?: boolean;
  onComplete?: () => void;
}

export function useLenis() {
  return {
    getLenis: () => instance,
    scrollTo(target: ScrollTarget, options: ScrollOptions = {}) {
      if (instance) {
        instance.scrollTo(target, { offset: -80, duration: 1.1, ...options });
        return;
      }
      const offset = options.offset ?? -80;
      const behavior: ScrollBehavior = options.immediate || document.documentElement.classList.contains('reduce-motion') ? 'auto' : 'smooth';
      if (typeof target === 'number') window.scrollTo({ top: target, behavior });
      else {
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY + offset, behavior });
      }
      options.onComplete?.();
    },
    stop: () => instance?.stop(),
    start: () => instance?.start(),
  };
}

/** 锁定 / 解锁页面滚动（浮层打开、转场进行时使用），兼容 Lenis 与原生滚动 */
let lockCount = 0;
export function lockScroll() {
  lockCount += 1;
  instance?.stop();
  document.documentElement.style.overflow = 'hidden';
}
export function unlockScroll() {
  lockCount = Math.max(0, lockCount - 1);
  if (lockCount === 0) {
    instance?.start();
    document.documentElement.style.overflow = '';
  }
}
