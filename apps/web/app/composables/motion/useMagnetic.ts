import { onMounted, onBeforeUnmount, type Ref } from 'vue';
import gsap from 'gsap';
import { MOTION } from './tokens';

/**
 * M7 磁吸（PRD 3.4）：光标进入元素 80px 半径就开始吸引，最多偏移 12px，离开时按 Token 缓动回弹。
 * 全站共用一个 pointermove 监听；元素位置在进入视口、滚动结束、尺寸变化时才重新测量（读写分离）。
 */
interface Magnet {
  el: HTMLElement;
  strength: number;
  rect: DOMRect | null;
  active: boolean;
  xTo: (v: number) => void;
  yTo: (v: number) => void;
}

const magnets = new Set<Magnet>();
let listening = false;
let measureQueued = false;

function measureAll() {
  measureQueued = false;
  magnets.forEach((m) => { m.rect = m.el.getBoundingClientRect(); });
}
function queueMeasure() {
  if (measureQueued) return;
  measureQueued = true;
  gsap.ticker.add(function once() {
    gsap.ticker.remove(once);
    measureAll();
  });
}

function onMove(e: PointerEvent) {
  if (e.pointerType !== 'mouse') return;
  magnets.forEach((m) => {
    const r = m.rect;
    if (!r) return;
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    // 到元素边框的距离（在元素内为 0）
    const ex = Math.max(0, Math.abs(dx) - r.width / 2);
    const ey = Math.max(0, Math.abs(dy) - r.height / 2);
    const edge = Math.hypot(ex, ey);
    if (edge < MOTION.magnetRadius) {
      // 越靠近越强，元素内部达到最大
      const pull = 1 - edge / MOTION.magnetRadius;
      const nx = dx / (r.width / 2 + MOTION.magnetRadius);
      const ny = dy / (r.height / 2 + MOTION.magnetRadius);
      m.xTo(nx * m.strength * (0.35 + 0.65 * pull));
      m.yTo(ny * m.strength * (0.35 + 0.65 * pull));
      m.active = true;
    } else if (m.active) {
      m.active = false;
      gsap.to(m.el, { x: 0, y: 0, duration: 0.7, ease: 'outBack', overwrite: 'auto' });
    }
  });
}

function ensureListening() {
  if (listening) return;
  listening = true;
  window.addEventListener('pointermove', onMove, { passive: true });
  window.addEventListener('scroll', queueMeasure, { passive: true });
  window.addEventListener('resize', queueMeasure, { passive: true });
}

export function useMagnetic(targetRef: Ref<HTMLElement | null>, strength: number = MOTION.magnetMax) {
  let magnet: Magnet | null = null;
  let ro: ResizeObserver | null = null;

  onMounted(() => {
    const el = targetRef.value;
    if (!el) return;
    if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    if (document.documentElement.classList.contains('reduce-motion')) return;
    magnet = {
      el,
      strength,
      rect: null,
      active: false,
      xTo: gsap.quickTo(el, 'x', { duration: 0.5, ease: 'outExpo' }),
      yTo: gsap.quickTo(el, 'y', { duration: 0.5, ease: 'outExpo' }),
    };
    magnets.add(magnet);
    ensureListening();
    ro = new ResizeObserver(queueMeasure);
    ro.observe(el);
    queueMeasure();
  });

  onBeforeUnmount(() => {
    ro?.disconnect();
    if (!magnet) return;
    magnets.delete(magnet);
    gsap.killTweensOf(magnet.el);
    gsap.set(magnet.el, { clearProps: 'transform' });
    magnet = null;
  });
}
