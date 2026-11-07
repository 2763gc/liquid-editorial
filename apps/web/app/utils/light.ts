/**
 * 四时光照 2.0：从四档变为连续（任务书 §4.5）
 *
 * 同一个函数既在 <head> 内联脚本里首屏前执行（nuxt.config 用 toString() 内联），
 * 也在运行时每 5 分钟校准一次。因此必须是不依赖任何外部变量的 ES5 纯函数：
 * 不用解构、默认参数、箭头函数，避免转译后引入辅助函数。
 *
 * 返回：
 * - period：当前时段（晨 / 昼 / 暮 / 夜）
 * - blend：相邻时段（只在晨↔昼、昼↔暮的分界前后 45 分钟内存在）
 * - t：与相邻时段的混合比例 0–0.5（分界点正好 50/50，两侧连续）
 * - angle：窗光角度，按本地时间估算太阳方位（不请求定位）；晨光从左上、暮光从右上
 * - warmth：-1（偏冷）… 0 … 1（偏暖）
 */
export interface LightState {
  period: 'morning' | 'day' | 'dusk' | 'night';
  blend: 'morning' | 'day' | 'dusk' | '';
  t: number;
  angle: number;
  warmth: number;
}

export function computeLight(minutes: number): LightState {
  var m = ((minutes % 1440) + 1440) % 1440;
  var h = m / 60;
  var period: LightState['period'] = h >= 5 && h < 10 ? 'morning' : h >= 10 && h < 17 ? 'day' : h >= 17 && h < 20 ? 'dusk' : 'night';
  var blend: LightState['blend'] = '';
  var t = 0;
  var W = 45;
  // 晨 | 昼 分界 10:00；昼 | 暮 分界 17:00。夜与晨、暮与夜之间是明暗主题切换，不做混合
  var edges = [[600, 'morning', 'day'], [1020, 'day', 'dusk']] as const;
  for (var i = 0; i < edges.length; i++) {
    var d = m - edges[i][0];
    if (d > -W && d < W) {
      blend = d < 0 ? edges[i][2] : edges[i][1];
      t = Math.round((0.5 * (1 - Math.abs(d) / W)) * 1000) / 1000;
    }
  }
  // 太阳方位：6:00 在东（左，110°），12:00 在正上（180°），18:00 在西（右，250°）
  var sun = Math.max(0, Math.min(1, (h - 6) / 12));
  var angle = Math.round(110 + sun * 140);
  // 色温：清晨偏冷，正午中性，傍晚偏暖；夜里是台灯的暖光
  var warmth = period === 'night' ? 0.6 : Math.round((h < 12 ? -0.6 * (1 - (h - 5) / 7) : Math.min(1, (h - 12) / 7)) * 100) / 100;
  return { period: period, blend: blend, t: t, angle: angle, warmth: warmth };
}

/** 写到 <html> 上：data-period / data-blend 选择色板，--light-* 驱动混合与窗光 */
export function applyLight(root: HTMLElement, s: LightState) {
  root.setAttribute('data-period', s.period);
  if (s.blend) root.setAttribute('data-blend', s.blend);
  else root.removeAttribute('data-blend');
  root.style.setProperty('--light-t', String(s.t));
  root.style.setProperty('--light-angle', `${s.angle}deg`);
  root.style.setProperty('--light-warmth', String(s.warmth));
}

export function nowMinutes(d = new Date()) {
  return d.getHours() * 60 + d.getMinutes();
}
