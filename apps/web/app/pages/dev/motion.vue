<script setup lang="ts">
import { ref } from 'vue';
import { useMagnetic } from '~/composables/motion/useMagnetic';
import { useSplitReveal } from '~/composables/motion/useSplitReveal';

const magneticBtnRef = ref<HTMLElement | null>(null);
useMagnetic(magneticBtnRef);

const revealContainerRef = ref<HTMLElement | null>(null);
useSplitReveal(revealContainerRef);

const copyText = ref('点击复制代码');
const isCopied = ref(false);

function handleCopy() {
  navigator.clipboard.writeText('npm install @blog/markdown');
  isCopied.value = true;
  copyText.value = '已复制！';
  setTimeout(() => {
    isCopied.value = false;
    copyText.value = '点击复制代码';
  }, 2000);
}

function setPeriod(period: string) {
  document.documentElement.setAttribute('data-period', period);
}

function replayCurtain() {
  sessionStorage.removeItem('seen_curtain');
  window.location.reload();
}
</script>

<template>
  <div class="motion-dev-container max-w-5xl mx-auto px-6 py-16">
    <header class="mb-12 pb-6 hairline-b">
      <div class="editorial-number mb-2">DEV VERIFICATION STAND</div>
      <h1 class="text-4xl font-bold font-serif">签名动效系统逐项验收走查展台</h1>
      <p class="text-xs text-[var(--color-ink-muted)] mt-2 font-mono">
        对照 PRD 3.4 节动效清单与 14.2 节设计规范逐条走查
      </p>
    </header>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-8 text-xs">
      <!-- M1 开场序幕 -->
      <section class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded flex flex-col justify-between">
        <div>
          <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M1 · 开场序幕 (Opening Curtain)</div>
          <p class="text-[var(--color-ink-muted)] mb-4 leading-relaxed">
            首次进入时的站名压印、000→100 计数与遮罩上揭。同一会话只播一次。
          </p>
        </div>
        <button
          @click="replayCurtain"
          class="px-4 py-2 bg-[var(--color-ink)] text-[var(--color-bg)] rounded font-mono hover:bg-[var(--color-accent)] transition-colors self-start"
        >
          重置缓存并重新播放 (M1)
        </button>
      </section>

      <!-- M7 磁吸按钮 -->
      <section class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded flex flex-col justify-between">
        <div>
          <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M7 · 磁吸按钮 (Magnetic Interaction)</div>
          <p class="text-[var(--color-ink-muted)] mb-4 leading-relaxed">
            光标距按钮 80px 范围内产生柔和引力吸附（最大 12px 偏移），松手弹性回弹。
          </p>
        </div>
        <div class="py-4">
          <button
            ref="magneticBtnRef"
            class="px-6 py-3 bg-[var(--color-accent)] text-white font-mono font-bold rounded shadow-lg will-change-transform"
          >
            Hover Me (磁吸按钮)
          </button>
        </div>
      </section>

      <!-- M6 上下文智能光标 -->
      <section class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded">
        <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M6 · 上下文光标 (Contextual Cursor)</div>
        <p class="text-[var(--color-ink-muted)] mb-4 leading-relaxed">
          桌面端 8px 实体圆点 + 32px 跟随圆环（lerp 0.15）。悬停不同区域呈现形态变化。
        </p>

        <div class="grid grid-cols-3 gap-2 text-center font-mono">
          <div data-cursor="read" class="p-4 bg-black/10 dark:bg-white/10 rounded cursor-pointer">
            悬停「阅读」
          </div>
          <div data-cursor="drag" class="p-4 bg-black/10 dark:bg-white/10 rounded cursor-pointer">
            悬停「拖拽」
          </div>
          <div data-cursor="zoom" class="p-4 bg-black/10 dark:bg-white/10 rounded cursor-pointer">
            悬停「放大」
          </div>
        </div>
      </section>

      <!-- M10 四时光照切换 -->
      <section class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded">
        <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M10 · 四时光照系统 (Diurnal Lighting)</div>
        <p class="text-[var(--color-ink-muted)] mb-4 leading-relaxed">
          界面按当地时间在晨、昼、暮、夜间平滑过渡色彩变量。点击下方手动预览：
        </p>

        <div class="grid grid-cols-4 gap-2 font-mono text-center">
          <button @click="setPeriod('morning')" class="py-2 bg-blue-500/20 text-blue-400 rounded">
            晨 05-10
          </button>
          <button @click="setPeriod('day')" class="py-2 bg-amber-500/20 text-amber-500 rounded">
            昼 10-17
          </button>
          <button @click="setPeriod('dusk')" class="py-2 bg-orange-500/20 text-orange-500 rounded">
            暮 17-20
          </button>
          <button @click="setPeriod('night')" class="py-2 bg-purple-500/20 text-purple-400 rounded">
            夜 20-05
          </button>
        </div>
      </section>

      <!-- M4 文字揭示 -->
      <section ref="revealContainerRef" class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded md:col-span-2">
        <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M4 · 文字逐行滑入揭示 (SplitText Reveal)</div>
        <h2 class="text-2xl font-bold font-serif mb-2">流体编辑部 · 优雅呼吸的文字排版</h2>
        <p class="text-[var(--color-ink-muted)] leading-relaxed">
          文字进入视口时从遮罩下向上滑入 28px，错峰跟随，只播放一次，杜绝无意义循环。
        </p>
      </section>

      <!-- M15 微交互集合 -->
      <section class="p-6 bg-[var(--color-surface)] border border-[var(--color-line)] rounded md:col-span-2 flex items-center justify-between">
        <div>
          <div class="font-mono font-bold text-[var(--color-accent)] mb-1">M15 · 微交互反馈 (Micro-Interactions)</div>
          <p class="text-[var(--color-ink-muted)]">点击按钮测试复制成功翻转反馈：</p>
        </div>

        <button
          @click="handleCopy"
          :class="[
            'px-5 py-2.5 rounded font-mono text-xs transition-all duration-200',
            isCopied ? 'bg-emerald-500 text-white font-bold' : 'bg-[var(--color-ink)] text-[var(--color-bg)]'
          ]"
        >
          {{ copyText }}
        </button>
      </section>
    </div>
  </div>
</template>
