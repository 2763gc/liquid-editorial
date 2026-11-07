<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useMotion } from '~/composables/useMotion';
import { useLenis } from '~/composables/useLenis';

/**
 * M9 横向章节（showcase 模板）：纵向滚动被映射为横向穿过每一章的扉页。
 * 每张扉页是一幅水墨 + 章节号 + 章节名，点击跳到正文对应位置。
 * 桌面端用 ScrollTrigger pin；窄屏、减弱动效时退化为可横向轻扫的轨道。
 */
interface TocItem { level: number; text: string; anchor: string }
const props = defineProps<{ toc: TocItem[]; seed: string; accent?: string | null }>();

const chapters = computed(() => props.toc.filter((t) => t.level === 2));
const wrapRef = ref<HTMLElement | null>(null);
const trackRef = ref<HTMLElement | null>(null);
const motion = useMotion();

function go(anchor: string) {
  const el = document.getElementById(anchor);
  if (el) useLenis().scrollTo(el, { offset: -96 });
}

onMounted(() => {
  const wrap = wrapRef.value;
  const track = trackRef.value;
  if (!wrap || !track || !motion.allows('parallax') || !window.matchMedia('(min-width: 900px)').matches) return;
  gsap.registerPlugin(ScrollTrigger);
  motion.ctx(wrap, () => {
    const distance = () => Math.max(0, track.scrollWidth - wrap.clientWidth);
    gsap.to(track, {
      x: () => -distance(),
      ease: 'none',
      scrollTrigger: {
        trigger: wrap,
        start: 'top top+=64',
        end: () => `+=${distance()}`,
        pin: true,
        scrub: 0.6,
        invalidateOnRefresh: true,
      },
    });
    // 每张扉页里的水墨随穿行轻微反向位移，像隔着一层水看
    track.querySelectorAll<HTMLElement>('.rail-art').forEach((art) => {
      gsap.fromTo(art, { xPercent: 8 }, {
        xPercent: -8,
        ease: 'none',
        scrollTrigger: { trigger: wrap, start: 'top top+=64', end: () => `+=${distance()}`, scrub: true },
      });
    });
  });
});
</script>

<template>
  <section v-if="chapters.length" ref="wrapRef" class="rail" aria-label="章节扉页">
    <div ref="trackRef" class="rail-track">
      <div class="rail-intro">
        <p class="eyebrow">Showcase · 章节</p>
        <p class="rail-intro-text">本期共 {{ chapters.length }} 章。向下滚动，横向翻过每一章的扉页。</p>
      </div>
      <button v-for="(c, i) in chapters" :key="c.anchor" type="button" class="rail-panel" data-cursor="read" @click="go(c.anchor)">
        <span class="rail-art"><InkCover :seed="`${seed}#${i}`" :no="i + 1" :accent="accent" :width="480" :height="560" :numeral="false" :seal="false" /></span>
        <span class="rail-no font-display">{{ String(i + 1).padStart(2, '0') }}</span>
        <span class="rail-title">{{ c.text }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.rail { position: relative; overflow: hidden; border-block: 1px solid var(--color-line); }
.rail-track {
  display: flex;
  gap: 1px;
  width: max-content;
  background: var(--color-line);
  will-change: transform;
}
.rail-intro,
.rail-panel { background: var(--color-bg); }
.rail-intro {
  width: min(420px, 80vw);
  padding: 48px var(--page-padding);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 14px;
}
.rail-intro-text { font-family: var(--font-serif); font-size: 18px; line-height: 1.8; color: var(--color-ink-muted); }
.rail-panel {
  position: relative;
  width: min(440px, 82vw);
  height: min(70vh, 620px);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 12px;
  padding: 32px;
  overflow: hidden;
  text-align: left;
}
.rail-art { position: absolute; inset: 0; opacity: 0.75; transition: opacity var(--dur-md) var(--ease-out-quart); }
.rail-panel:hover .rail-art { opacity: 1; }
.rail-no {
  position: relative;
  font-size: clamp(80px, 9vw, 140px);
  font-style: italic;
  font-weight: 300;
  line-height: 0.8;
  letter-spacing: -0.05em;
  color: var(--color-accent);
  font-variation-settings: "opsz" 144, "SOFT" 100;
}
.rail-title {
  position: relative;
  max-width: 12em;
  font-family: var(--font-serif);
  font-size: clamp(22px, 2vw, 30px);
  font-weight: 900;
  line-height: 1.3;
  padding: 10px 12px;
  margin: -10px -12px;
  background: color-mix(in oklab, var(--color-bg) 78%, transparent);
}
@media (max-width: 899px), (prefers-reduced-motion: reduce) {
  .rail { overflow-x: auto; scroll-snap-type: x mandatory; }
  .rail-panel { scroll-snap-align: start; height: 420px; }
}
</style>
