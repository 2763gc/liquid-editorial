/**
 * 动效 Token 的唯一来源（docs/motion.md）
 *
 * - CSS 变量由 motionCss() 生成，在 nuxt.config 中内联进 <head>，tokens.css 不再重复定义
 * - GSAP 侧由 plugins/motion.client.ts 用 CustomEase 注册同名缓动：outExpo、inOutQuart……
 *   组件里只写 ease: 'outExpo'，不再出现 power3 / expo.out / elastic 等散落的字符串
 * 本文件不能引入任何运行时依赖：nuxt.config 在构建期直接导入它。
 */

/** 三次贝塞尔缓动；名称与 CSS 变量一一对应：outExpo → --ease-out-expo */
export const EASE = {
  /** 进入：快起慢收，几乎所有「出现」都用它 */
  outExpo: [0.16, 1, 0.3, 1],
  /** 转场、遮罩、走纸：两端都慢，中段推进 */
  inOutQuart: [0.76, 0, 0.24, 1],
  /** 微交互回弹（磁吸复位、印章落定） */
  outBack: [0.34, 1.56, 0.64, 1],
  outQuart: [0.25, 1, 0.5, 1],
  /** 离开：比进入更快、更干脆 */
  inQuart: [0.5, 0, 0.75, 0],
  outCirc: [0, 0.55, 0.45, 1],
  /** 压印：极短的冲击后迅速落定 */
  impress: [0.2, 0.9, 0.1, 1],
} as const satisfies Record<string, readonly [number, number, number, number]>;

/** 克制的弹簧：约 1.7% 过冲后静止，用于指示器、胶囊等「有质量」的元素（CSS 用 linear()，GSAP 用折线路径） */
export const SPRING: ReadonlyArray<readonly [number, number]> = [
  [0, 0], [0.014, 0.006], [0.028, 0.025], [0.061, 0.101], [0.189, 0.539], [0.253, 0.721], [0.315, 0.849],
  [0.381, 0.937], [0.418, 0.968], [0.457, 0.991], [0.501, 1.006], [0.55, 1.015], [0.639, 1.017], [1, 1],
];

/** 时长（毫秒） */
export const DUR = {
  micro: 180,
  sm: 350,
  md: 700,
  lg: 1000,
  page: 900,
  /** 压印：字重由细到目标值、scale 1.015→1 */
  impress: 240,
  /** 走纸：一张纸从底边走到顶边（转场的一半） */
  feed: 420,
  /** 首屏光照过渡（PRD 2.2） */
  light: 2000,
} as const;

/** 错峰（毫秒）：同组 ≤ 60ms，整组 ≤ 400ms（任务书 §7） */
export const STAGGER = { char: 40, list: 60, card: 80, groupMax: 400 } as const;

/** 语义参数 */
export const MOTION = {
  /** 套准错位：常态 3px，上限 6px，持续 ≤ 300ms */
  registerOffset: 3,
  registerMax: 6,
  /** M8 速度形变：最大 ±2°（PRD 允许 ±4°，取一半） */
  skewMax: 2,
  /** M7 磁吸：80px 半径内开始吸引，最多偏移 12px */
  magnetRadius: 80,
  magnetMax: 12,
  /** 悬停意图：进入前防抖、进入慢、离开快 */
  hoverIntent: 60,
  hoverIn: 500,
  hoverOut: 300,
  /** 预取：悬停 100ms 后预取目标页 */
  prefetchDelay: 100,
} as const;

export type EaseName = keyof typeof EASE | 'spring';

function kebab(name: string) {
  return name.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`);
}

export function bezierCss(b: readonly number[]) {
  return `cubic-bezier(${b.join(', ')})`;
}

export function springCss() {
  return `linear(${SPRING.map(([x, y]) => `${y} ${+(x * 100).toFixed(1)}%`).join(', ')})`;
}

/** GSAP CustomEase 可直接使用的 SVG 路径 */
export function easePath(name: EaseName) {
  if (name === 'spring') return `M0,0 ${SPRING.slice(1).map(([x, y]) => `L${x},${y}`).join(' ')}`;
  const [x1, y1, x2, y2] = EASE[name];
  return `M0,0 C${x1},${y1} ${x2},${y2} 1,1`;
}

/** 生成 :root 上的全部动效变量 */
export function motionCss() {
  const lines: string[] = [];
  for (const [name, b] of Object.entries(EASE)) lines.push(`--ease-${kebab(name)}:${bezierCss(b)}`);
  lines.push(`--ease-spring:${springCss()}`);
  for (const [name, ms] of Object.entries(DUR)) lines.push(`--dur-${name}:${ms}ms`);
  lines.push(`--stagger:${STAGGER.list}ms`, `--stagger-char:${STAGGER.char}ms`, `--stagger-card:${STAGGER.card}ms`);
  lines.push(`--register-offset:${MOTION.registerOffset}px`, `--register-max:${MOTION.registerMax}px`);
  return `:root{${lines.join(';')}}`;
}

/** 秒（GSAP 用） */
export const sec = (ms: number) => ms / 1000;

/** 整组错峰不超过上限 */
export function staggerFor(count: number, each: number = STAGGER.list) {
  if (count <= 1) return 0;
  return Math.min(each, STAGGER.groupMax / (count - 1)) / 1000;
}

/** 与帧率无关的插值系数：k 为 60fps 下每帧的系数 */
export function frameLerp(k: number, dtMs: number) {
  return 1 - Math.pow(1 - k, dtMs / (1000 / 60));
}
