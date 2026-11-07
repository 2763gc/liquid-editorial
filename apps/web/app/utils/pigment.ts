/**
 * 设色：把文章的强调色映射到最接近的传统国画颜料（docs/design-v2.md）
 * 数据库里的强调色是任意 hex（蓝、紫、粉……），直接用会和水墨、朱砂打架；
 * 按色相就近取一种矿物 / 植物颜料，明度与彩度都收敛到同一档，全站气质一致。
 * 印章始终是朱砂，不参与映射。
 */
export interface Pigment {
  name: string;
  /** 色块、墨点、粗线 */
  color: string;
  /** 小字号文字：对纸色 ≥ 4.5:1 */
  text: string;
  /** 夜间版本 */
  night: string;
}

const PIGMENTS: Array<{ hue: number } & Pigment> = [
  { hue: 30, name: '朱砂', color: 'oklch(64% 0.19 33)', text: 'oklch(53% 0.18 33)', night: 'oklch(68% 0.18 34)' },
  { hue: 8, name: '胭脂', color: 'oklch(58% 0.15 8)', text: 'oklch(50% 0.15 8)', night: 'oklch(68% 0.13 8)' },
  { hue: 70, name: '赭石', color: 'oklch(60% 0.12 60)', text: 'oklch(50% 0.11 60)', night: 'oklch(70% 0.11 62)' },
  { hue: 90, name: '藤黄', color: 'oklch(76% 0.13 88)', text: 'oklch(52% 0.11 85)', night: 'oklch(80% 0.12 90)' },
  { hue: 160, name: '石绿', color: 'oklch(62% 0.09 165)', text: 'oklch(48% 0.08 165)', night: 'oklch(72% 0.09 165)' },
  { hue: 225, name: '花青', color: 'oklch(56% 0.08 225)', text: 'oklch(47% 0.08 228)', night: 'oklch(70% 0.08 225)' },
  { hue: 255, name: '石青', color: 'oklch(52% 0.11 258)', text: 'oklch(47% 0.11 258)', night: 'oklch(70% 0.1 258)' },
  { hue: 300, name: '青莲', color: 'oklch(52% 0.1 305)', text: 'oklch(47% 0.1 305)', night: 'oklch(70% 0.09 305)' },
];

function hueOf(hex: string) {
  const n = parseInt(hex.replace('#', '').slice(0, 6), 16);
  if (Number.isNaN(n)) return 30;
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => lin(v / 255));
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  const A = 1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s;
  const B = 0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s;
  const h = (Math.atan2(B, A) * 180) / Math.PI;
  return h < 0 ? h + 360 : h;
}

export function pigmentFor(hex?: string | null): Pigment {
  if (!hex) return PIGMENTS[0];
  const h = hueOf(hex);
  let best = PIGMENTS[0];
  let bestD = 999;
  for (const p of PIGMENTS) {
    const d = Math.min(Math.abs(p.hue - h), 360 - Math.abs(p.hue - h));
    if (d < bestD) { bestD = d; best = p; }
  }
  return best;
}

/** 编辑器里可选的设色（存进数据库的 hex 取自上面每种颜料的「color」） */
export const PIGMENT_SWATCHES: Array<{ name: string; hex: string }> = [
  { name: '朱砂', hex: '#E85336' },
  { name: '胭脂', hex: '#C14D69' },
  { name: '赭石', hex: '#B36D2A' },
  { name: '藤黄', hex: '#D3AC41' },
  { name: '石绿', hex: '#4B9779' },
  { name: '花青', hex: '#387E98' },
  { name: '石青', hex: '#3F69A7' },
  { name: '青莲', hex: '#765997' },
];
