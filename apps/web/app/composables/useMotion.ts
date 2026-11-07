import { reactive, readonly, onBeforeUnmount, getCurrentInstance } from 'vue';
import gsap from 'gsap';
import { DUR, EASE, STAGGER, MOTION, sec, staggerFor, frameLerp, type EaseName } from '~/composables/motion/tokens';

export type Tier = 'high' | 'mid' | 'low';

/**
 * 动效引擎的唯一入口（任务书 §4.3）
 * - tier：设备档位。首屏由 boot.ts 按硬件启发式写入 data-tier，plugins/motion.client.ts 再按首帧耗时修正
 * - reduced：系统偏好或站内开关；切换时同步 html.reduce-motion 与 Lenis
 * - touch：粗指针设备。不渲染自定义光标与磁吸，悬停改为按压反馈
 * - ctx(scope, fn)：包装 gsap.context，组件卸载时自动 revert，ScrollTrigger 不会泄漏
 */
const state = reactive({
  tier: 'high' as Tier,
  reduced: false,
  touch: false,
  ready: false,
});

let reducedListeners: Array<(v: boolean) => void> = [];

export function initMotionState() {
  const root = document.documentElement;
  state.tier = (root.getAttribute('data-tier') as Tier) || 'high';
  state.reduced = root.classList.contains('reduce-motion');
  state.touch = root.getAttribute('data-pointer') === 'coarse';
  state.ready = true;
}

export function setTier(tier: Tier) {
  state.tier = tier;
  document.documentElement.setAttribute('data-tier', tier);
}

export function onReducedChange(fn: (v: boolean) => void) {
  reducedListeners.push(fn);
  return () => { reducedListeners = reducedListeners.filter((f) => f !== fn); };
}

export function setReduced(next: boolean) {
  const root = document.documentElement;
  state.reduced = next;
  root.classList.toggle('reduce-motion', next);
  root.classList.toggle('motion-ready', !next);
  try {
    if (next) localStorage.setItem('blog_reduce_motion', '1');
    else localStorage.removeItem('blog_reduce_motion');
  } catch {}
  reducedListeners.forEach((fn) => fn(next));
}

export function useMotion() {
  const instance = getCurrentInstance();
  const contexts: gsap.Context[] = [];
  if (instance) onBeforeUnmount(() => contexts.forEach((c) => c.revert()));

  return {
    state: readonly(state),
    DUR,
    EASE,
    STAGGER,
    MOTION,
    sec,
    staggerFor,
    frameLerp,
    /** 是否允许某类效果：'webgl' 只在高中档、'parallax' 不在低档、全部受减弱动效约束 */
    allows(feature: 'webgl' | 'parallax' | 'cursor' | 'skew' | 'transition') {
      if (state.reduced) return false;
      if (feature === 'cursor') return !state.touch;
      if (feature === 'webgl') return state.tier !== 'low' && !state.touch;
      if (feature === 'parallax' || feature === 'skew') return state.tier !== 'low';
      return true;
    },
    ease(name: EaseName) {
      return name;
    },
    setReduced,
    /** gsap.context 包装：在 scope 内创建的动画与 ScrollTrigger 会在卸载时一起 revert */
    ctx(scope: Element | string | null | undefined, fn: (self: gsap.Context) => void) {
      const c = gsap.context(fn, scope || undefined);
      contexts.push(c);
      return c;
    },
  };
}
