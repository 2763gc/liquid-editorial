import { ref, readonly } from 'vue';
import { computeLight, applyLight, nowMinutes, type LightState } from '~/utils/light';

export type ThemeMode = 'auto' | 'light' | 'dark';
export type Period = LightState['period'];

/*
 * 主题状态（全站单例）
 * 服务端与水合阶段一律使用默认值（自动 · 昼），挂载后再由 initTheme() 读取本地偏好与时间——
 * 依赖时间与 localStorage 的内容不能参与 SSR，否则会出现 hydration 不一致（B27）。
 * 首屏的真实主题早已由 <head> 内联脚本写在 <html> 上，这里只是让界面文案跟上。
 */
const mode = ref<ThemeMode>('auto');
const resolved = ref<'light' | 'dark'>('light');
const period = ref<Period>('day');
const ready = ref(false);
/** 后台等拥有独立明暗偏好的区域在此「接管」data-theme；为 null 时跟随前台偏好 */
let override: 'light' | 'dark' | null = null;
let timer: number | undefined;

function apply() {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  const light = computeLight(nowMinutes());
  period.value = light.period;
  resolved.value = mode.value === 'auto' ? (light.period === 'night' ? 'dark' : 'light') : mode.value;
  applyLight(root, light);
  root.setAttribute('data-mode', mode.value);
  // 定时校准四时光照时也会走到这里，必须尊重接管，否则后台会被悄悄切回前台的昼夜
  root.setAttribute('data-theme', override ?? resolved.value);
}

/** 由 plugins/theme.client.ts 在 app:mounted 时调用 */
export function initTheme() {
  if (ready.value) return;
  let saved: string | null = null;
  try { saved = localStorage.getItem('blog_theme'); } catch {}
  mode.value = saved === 'light' || saved === 'dark' ? saved : 'auto';
  if (location.pathname.startsWith('/admin')) {
    try { override = localStorage.getItem('blog_admin_theme') === 'light' ? 'light' : 'dark'; } catch { override = 'dark'; }
  }
  // 首屏的光照缓动（boot.ts）还在进行时不要立刻覆盖
  const root = document.documentElement;
  if (root.classList.contains('light-easing')) {
    const light = computeLight(nowMinutes());
    period.value = light.period;
    resolved.value = mode.value === 'auto' ? (light.period === 'night' ? 'dark' : 'light') : mode.value;
  } else {
    apply();
  }
  ready.value = true;
  // 每 5 分钟校准一次光照：单次变化肉眼察觉不到，一整天里光线在流动
  window.clearInterval(timer);
  timer = window.setInterval(apply, 5 * 60 * 1000);
}

/** 晕染边缘的遮罩：一个被噪声扰动过边缘的圆（墨在纸纤维里洇开） */
const BLEED_MASK = `url("data:image/svg+xml,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200'><filter id='b' x='-20%' y='-20%' width='140%' height='140%'><feTurbulence type='fractalNoise' baseFrequency='0.045' numOctaves='3' seed='7'/><feDisplacementMap in='SourceGraphic' scale='22' xChannelSelector='R' yChannelSelector='G'/><feGaussianBlur stdDeviation='0.8'/></filter><circle cx='100' cy='100' r='70' filter='url(#b)'/></svg>",
)}")`;

/**
 * 主题切换：保留从按钮处圆形扩散的方式，边缘改为不规则的晕染。
 * 不支持 View Transitions 或减弱动效时直接切换；切换期间冻结全站颜色过渡，避免快照之后颜色再「补一次」动画。
 */
export function runThemeTransition(update: () => void, origin?: { x: number; y: number }) {
  const root = document.documentElement;
  const doc = document as Document & { startViewTransition?: (cb: () => void) => { ready: Promise<void>; finished: Promise<void> } };
  if (!doc.startViewTransition || root.classList.contains('reduce-motion')) {
    update();
    return;
  }

  const btn = document.querySelector<HTMLElement>('.theme-toggle')?.getBoundingClientRect();
  const x = origin?.x ?? (btn ? btn.left + btn.width / 2 : window.innerWidth - 80);
  const y = origin?.y ?? (btn ? btn.top + btn.height / 2 : 32);
  // 遮罩里的圆半径是画布的 35%，要盖住最远的角，尺寸需放大到 半径 / 0.35
  const r = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
  const size = (r / 0.35) * 1.08;

  root.classList.add('theme-switching');
  const vt = doc.startViewTransition(update);
  vt.ready.then(() => {
    const supportsMask = CSS.supports('mask-image', BLEED_MASK) || CSS.supports('-webkit-mask-image', BLEED_MASK);
    if (supportsMask) {
      root.animate(
        {
          maskImage: [BLEED_MASK, BLEED_MASK],
          webkitMaskImage: [BLEED_MASK, BLEED_MASK],
          maskRepeat: ['no-repeat', 'no-repeat'],
          webkitMaskRepeat: ['no-repeat', 'no-repeat'],
          maskSize: ['0px 0px', `${size}px ${size}px`],
          webkitMaskSize: ['0px 0px', `${size}px ${size}px`],
          maskPosition: [`${x}px ${y}px`, `${x - size / 2}px ${y - size / 2}px`],
          webkitMaskPosition: [`${x}px ${y}px`, `${x - size / 2}px ${y - size / 2}px`],
        } as unknown as Keyframe[],
        { duration: 820, easing: 'cubic-bezier(0.76, 0, 0.24, 1)', pseudoElement: '::view-transition-new(root)' },
      );
    } else {
      root.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${r}px at ${x}px ${y}px)`] },
        { duration: 760, easing: 'cubic-bezier(0.76, 0, 0.24, 1)', pseudoElement: '::view-transition-new(root)' },
      );
    }
  }).catch(() => {});
  vt.finished.finally(() => root.classList.remove('theme-switching'));
}

export function useTheme() {
  function persist(next: ThemeMode) {
    mode.value = next;
    try {
      if (next === 'auto') localStorage.removeItem('blog_theme');
      else localStorage.setItem('blog_theme', next);
    } catch {}
  }

  /** 切换主题；只有实际明暗发生变化时才播放晕染扩散 */
  function setMode(next: ThemeMode, origin?: { x: number; y: number }) {
    const target = next === 'auto' ? (computeLight(nowMinutes()).period === 'night' ? 'dark' : 'light') : next;
    const update = () => {
      persist(next);
      apply();
    };
    if (target === resolved.value) update();
    else runThemeTransition(update, origin);
  }

  /** 自动 → 昼 → 夜 → 自动 */
  function cycle(origin?: { x: number; y: number }) {
    setMode(mode.value === 'auto' ? 'light' : mode.value === 'light' ? 'dark' : 'auto', origin);
  }

  return {
    mode: readonly(mode),
    resolved: readonly(resolved),
    period: readonly(period),
    ready: readonly(ready),
    setMode,
    cycle,
    /** 接管 / 归还 data-theme：进入后台时传入后台偏好，离开后台时传 null 还原前台偏好 */
    setOverride(next: 'light' | 'dark' | null) {
      override = next;
      apply();
    },
  };
}
