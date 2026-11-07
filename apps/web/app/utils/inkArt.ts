/**
 * 生成式水墨封面（docs/design-v2.md §2）
 * 同一个 slug 永远得到同一幅画：远山、墨晕、皴笔、折枝、孤月五种构图，
 * 墨的浓淡分层，边缘由 SVG 湍流滤镜扰动成「洇」的样子；右下角钤一方朱砂期号印。
 * 纯函数：服务端渲染与客户端水合得到完全相同的结构（不会 hydration 不一致）。
 */

export type InkVariant = 'mountain' | 'bloom' | 'stroke' | 'branch' | 'moon';

export interface InkShape {
  d?: string;
  cx?: number;
  cy?: number;
  r?: number;
  /** 0–1 的墨浓度，对应 CSS 中的透明度 */
  tone: number;
  kind: 'fill' | 'stroke' | 'ring';
  width?: number;
  /** 使用哪一层滤镜：wet（湿墨晕）、dry（枯笔皴）、soft（只柔化边缘，保持形状，如月轮） */
  filter: 'wet' | 'dry' | 'soft';
  accent?: boolean;
}

export interface InkArt {
  variant: InkVariant;
  seed: number;
  shapes: InkShape[];
  seal: { x: number; y: number; rot: number };
}

export const VARIANTS: InkVariant[] = ['mountain', 'bloom', 'stroke', 'branch', 'moon'];

export function hashSeed(text: string) {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed: number) {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return (s >>> 0) / 4294967296;
  };
}

const f = (n: number) => Math.round(n * 10) / 10;

/** 平滑的山脊：若干正弦叠加 + 随机相位 */
function ridge(r: () => number, w: number, h: number, base: number, amp: number) {
  const k1 = 1 + r() * 2.2;
  const k2 = 3 + r() * 4;
  const p1 = r() * 6.28;
  const p2 = r() * 6.28;
  const steps = 24;
  let d = `M0 ${h}`;
  for (let i = 0; i <= steps; i++) {
    const x = (w * i) / steps;
    const t = i / steps;
    const y = base - amp * (0.62 * Math.sin(t * Math.PI * k1 + p1) + 0.38 * Math.sin(t * Math.PI * k2 + p2)) - amp * 0.6 * Math.sin(t * Math.PI);
    d += ` L${f(x)} ${f(y)}`;
  }
  return `${d} L${w} ${h} Z`;
}

/**
 * 一笔：沿二次贝塞尔曲线取样，两侧按 sin(πt)^0.6 收放笔锋，得到起笔细、行笔粗、收笔尖的闭合笔触
 */
function brush(x0: number, y0: number, cx: number, cy: number, x1: number, y1: number, width: number, steps = 28) {
  const left: string[] = [];
  const right: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const x = u * u * x0 + 2 * u * t * cx + t * t * x1;
    const y = u * u * y0 + 2 * u * t * cy + t * t * y1;
    const dx = 2 * u * (cx - x0) + 2 * t * (x1 - cx);
    const dy = 2 * u * (cy - y0) + 2 * t * (y1 - cy);
    const len = Math.hypot(dx, dy) || 1;
    // 起笔略重于收笔
    const half = (width / 2) * Math.pow(Math.sin(Math.PI * Math.min(1, t * 1.08)), 0.6) * (1.1 - t * 0.35);
    const nx = (-dy / len) * half;
    const ny = (dx / len) * half;
    left.push(`${f(x + nx)} ${f(y + ny)}`);
    right.unshift(`${f(x - nx)} ${f(y - ny)}`);
  }
  return `M${left.join(' L')} L${right.join(' L')} Z`;
}

function curve(r: () => number, w: number, h: number) {
  const x0 = r() * w * 0.3;
  const y0 = h * (0.35 + r() * 0.5);
  const x3 = w * (0.65 + r() * 0.35);
  const y3 = h * (0.1 + r() * 0.6);
  return `M${f(x0)} ${f(y0)} C${f(w * (0.2 + r() * 0.3))} ${f(h * r())} ${f(w * (0.4 + r() * 0.3))} ${f(h * r())} ${f(x3)} ${f(y3)}`;
}

export function inkArt(seedText: string, w = 400, h = 250, prefer?: InkVariant): InkArt {
  const seed = hashSeed(seedText);
  const r = rng(seed);
  const variant = prefer || VARIANTS[seed % VARIANTS.length];
  const shapes: InkShape[] = [];

  if (variant === 'mountain') {
    // 三重远山：越远越淡，山脚有一抹雾
    shapes.push({ d: ridge(r, w, h, h * 0.52, h * 0.16), tone: 0.14, kind: 'fill', filter: 'wet' });
    shapes.push({ d: ridge(r, w, h, h * 0.68, h * 0.14), tone: 0.3, kind: 'fill', filter: 'wet' });
    shapes.push({ d: ridge(r, w, h, h * 0.86, h * 0.1), tone: 0.62, kind: 'fill', filter: 'dry' });
    shapes.push({ cx: w * (0.62 + r() * 0.25), cy: h * (0.18 + r() * 0.12), r: h * 0.07, tone: 0.75, kind: 'fill', filter: 'wet', accent: true });
  } else if (variant === 'bloom') {
    // 墨晕：几团湿墨，最大的一团留下一圈水痕
    const n = 3 + Math.floor(r() * 3);
    for (let i = 0; i < n; i++) {
      shapes.push({ cx: w * r(), cy: h * (0.2 + r() * 0.7), r: h * (0.16 + r() * 0.34), tone: 0.12 + r() * 0.34, kind: 'fill', filter: 'wet' });
    }
    shapes.push({ cx: w * (0.3 + r() * 0.4), cy: h * (0.4 + r() * 0.3), r: h * 0.36, tone: 0.5, kind: 'ring', width: 1.6, filter: 'wet' });
    shapes.push({ cx: w * (0.15 + r() * 0.7), cy: h * (0.2 + r() * 0.6), r: h * 0.035, tone: 0.9, kind: 'fill', filter: 'wet', accent: true });
  } else if (variant === 'stroke') {
    // 皴笔：一道浓墨主笔横扫，两道淡墨顺势带过，飞白由枯笔滤镜撕出
    const y = h * (0.42 + r() * 0.2);
    const x0 = w * (0.04 + r() * 0.12);
    const x1 = w * (0.84 + r() * 0.12);
    const bend = (r() - 0.5) * h * 0.5;
    shapes.push({ d: brush(x0, y, (x0 + x1) / 2, y + bend, x1, y - bend * 0.3, h * (0.14 + r() * 0.08)), tone: 0.82, kind: 'fill', filter: 'dry' });
    for (let i = 0; i < 2; i++) {
      const yy = y + (i ? 1 : -1) * h * (0.16 + r() * 0.1);
      const a = w * (0.15 + r() * 0.3);
      const b = w * (0.6 + r() * 0.35);
      shapes.push({ d: brush(a, yy, (a + b) / 2, yy + (r() - 0.5) * h * 0.3, b, yy + (r() - 0.5) * h * 0.12, h * (0.05 + r() * 0.05)), tone: 0.28 + r() * 0.2, kind: 'fill', filter: 'dry' });
    }
    shapes.push({ cx: w * (0.12 + r() * 0.76), cy: h * (0.16 + r() * 0.12), r: h * 0.03, tone: 0.9, kind: 'fill', filter: 'wet', accent: true });
  } else if (variant === 'branch') {
    // 折枝：一枝斜出（有笔锋），一枝细枝，几点花苞
    const sx = w * (0.02 + r() * 0.12);
    const sy = h * (0.7 + r() * 0.25);
    const ex = w * (0.7 + r() * 0.28);
    const ey = h * (0.08 + r() * 0.3);
    shapes.push({ d: brush(sx, sy, w * (0.3 + r() * 0.2), h * (0.2 + r() * 0.5), ex, ey, h * 0.05), tone: 0.8, kind: 'fill', filter: 'dry' });
    shapes.push({ d: curve(r, w, h), tone: 0.34, kind: 'stroke', width: 1.2 + r() * 1.6, filter: 'dry' });
    const buds = 4 + Math.floor(r() * 4);
    for (let i = 0; i < buds; i++) {
      shapes.push({ cx: w * (0.25 + r() * 0.65), cy: h * (0.12 + r() * 0.6), r: 3 + r() * 6, tone: 0.85, kind: 'fill', filter: 'wet', accent: i < 2 });
    }
    shapes.push({ cx: w * 0.8, cy: h * 0.75, r: h * 0.4, tone: 0.1, kind: 'fill', filter: 'wet' });
  } else {
    // 孤月：一轮淡月（月面淡墨 + 一圈月晕），几道横云，山脚一线远山
    shapes.push({ d: ridge(r, w, h, h * 0.95, h * 0.08), tone: 0.34, kind: 'fill', filter: 'wet' });
    const mcx = w * (0.6 + r() * 0.24);
    const mcy = h * (0.28 + r() * 0.12);
    const mr = h * (0.15 + r() * 0.05);
    shapes.push({ cx: mcx, cy: mcy, r: mr * 1.5, tone: 0.06, kind: 'fill', filter: 'soft' });
    shapes.push({ cx: mcx, cy: mcy, r: mr, tone: 0.16, kind: 'fill', filter: 'soft' });
    shapes.push({ cx: mcx, cy: mcy, r: mr, tone: 0.5, kind: 'ring', width: 1.2, filter: 'soft' });
    for (let i = 0; i < 3; i++) {
      const y = h * (0.56 + i * 0.12 + r() * 0.04);
      const a = -w * 0.05 + r() * w * 0.2;
      const b = w * (0.7 + r() * 0.35);
      shapes.push({ d: brush(a, y, (a + b) / 2, y - h * (0.04 + r() * 0.08), b, y + (r() - 0.5) * h * 0.06, h * (0.05 + i * 0.03)), tone: 0.12 + i * 0.12, kind: 'fill', filter: 'wet' });
    }
  }

  return {
    variant,
    seed,
    shapes,
    seal: { x: w - 22 - r() * 18, y: h - 22 - r() * 14, rot: f((r() - 0.5) * 8) },
  };
}

/** 文章模板 → 封面构图 */
export function variantForLayout(layout?: string | null): InkVariant | undefined {
  return ({ standard: undefined, wide: 'mountain', immersive: 'moon', essay: 'branch', showcase: 'bloom' } as Record<string, InkVariant | undefined>)[layout || 'standard'];
}
