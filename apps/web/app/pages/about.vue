<script setup lang="ts">
import { ref } from 'vue';

useHead({ title: "关于 · Luntrix's Editorial" });

const EMAIL = 'luntrix@editorial.dev';
const copied = ref(false);

async function copyEmail() {
  try {
    await navigator.clipboard.writeText(EMAIL);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch {}
}

// 技术栈元素周期表（PRD 5.11：不使用技能进度条）
const techPeriodicTable = [
  { symbol: 'Rs', name: 'Rust', years: '4', category: 'Systems', desc: '异步运行时 / 高性能服务' },
  { symbol: 'Ts', name: 'TypeScript', years: '7', category: 'Frontend', desc: '严格类型体操 / 全栈系统' },
  { symbol: 'Vu', name: 'Vue 3', years: '6', category: 'Frontend', desc: 'Nuxt 4 / 响应式系统重构' },
  { symbol: 'Py', name: 'Python', years: '8', category: 'Backend', desc: 'FastAPI / 算法与数据处理' },
  { symbol: 'Sq', name: 'SQLite', years: '5', category: 'Database', desc: 'WAL 模式 / FTS5 引擎' },
  { symbol: 'Gl', name: 'WebGL', years: '3', category: 'Graphics', desc: 'Three.js / GLSL 流体着色器' },
  { symbol: 'Go', name: 'Go', years: '4', category: 'Backend', desc: '微服务调度 / 并发工具链' },
  { symbol: 'Lx', name: 'Linux', years: '9', category: 'DevOps', desc: '内核调试 / 容器编排' },
];

const timeline = [
  { year: '2026', role: '系统架构师 & 数字产品作者', desc: '主导空间化数字阅读系统 Liquid Editorial 的开源与演进。' },
  { year: '2023 — 2025', role: '资深全栈研发工程师', desc: '深耕大规模高并发服务端架构与富交互 Web 前端工程化。' },
  { year: '2020 — 2023', role: '分布式系统工程师', desc: '负责分布式日志与嵌入式 LSM-Tree 存储引擎的性能调优。' },
  { year: '2016 — 2020', role: '计算机科学学士', desc: '专注于操作系统底层架构与计算机图形学研究。' },
];
</script>

<template>
  <div class="about-page">
    <UiPageMasthead
      index="07"
      en="About the Author"
      label="关于作者"
      title="探索系统架构、数字美学与会呼吸的代码。"
      size="md"
    >
      <div class="about-actions">
        <button type="button" class="btn btn-solid" @click="copyEmail">
          <Transition name="swap-y" mode="out-in">
            <span :key="String(copied)">{{ copied ? `已复制 ${EMAIL}` : '复制联系邮箱' }}</span>
          </Transition>
        </button>
        <a href="https://github.com" target="_blank" rel="noopener" class="btn">GitHub <span class="btn-arrow is-up" aria-hidden="true">↗</span></a>
      </div>
    </UiPageMasthead>

    <div class="page-shell">
      <!-- 自述 -->
      <section class="about-section" aria-labelledby="about-intro">
        <h2 id="about-intro" class="about-label"><span>01</span>自述</h2>
        <div class="about-intro">
          <p v-reveal class="reveal about-lead">
            我是 Luntrix，一名软件开发者。热衷于在操作系统底层与前端视觉交互之间寻找平衡。
          </p>
          <p v-reveal="100" class="reveal">
            追求严谨的工程抽象与杂志级排版美感，坚信代码本身就是一门具有雕塑感的艺术。这份刊物记录我在系统、工具与界面之间来回穿行时留下的笔记。
          </p>
        </div>
      </section>

      <!-- 技术栈周期表 -->
      <section class="about-section" aria-labelledby="about-stack">
        <h2 id="about-stack" class="about-label"><span>02</span>技术栈周期表</h2>
        <div>
          <div v-reveal class="periodic hairline-grid reveal">
            <div
              v-for="(el, i) in techPeriodicTable"
              :key="el.symbol"
              class="element"
              tabindex="0"
            >
              <div class="element-top">
                <span>{{ String(i + 1).padStart(2, '0') }}</span>
                <span>{{ el.years }} 年</span>
              </div>
              <div class="element-symbol font-display">{{ el.symbol }}</div>
              <div class="element-name">{{ el.name }}</div>
              <p class="element-desc">{{ el.desc }}</p>
              <span class="element-cat">{{ el.category }}</span>
            </div>
          </div>
          <p class="periodic-note">数字为实际使用年限；不画进度条，因为熟练度从来不是一条直线。</p>
        </div>
      </section>

      <!-- 经历 -->
      <section class="about-section" aria-labelledby="about-timeline">
        <h2 id="about-timeline" class="about-label"><span>03</span>经历脉络</h2>
        <ol class="trajectory">
          <li v-for="(item, i) in timeline" :key="item.year" v-reveal="i * 60" class="trajectory-item reveal">
            <span class="trajectory-year">{{ item.year }}</span>
            <div>
              <h3 class="trajectory-role">{{ item.role }}</h3>
              <p class="trajectory-desc">{{ item.desc }}</p>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<style scoped>
.about-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.about-actions .btn { height: 44px; padding: 0 22px; }
.swap-y-enter-active, .swap-y-leave-active { transition: transform 360ms var(--ease-out-expo), opacity 220ms ease; }
.swap-y-enter-from { transform: translateY(60%); opacity: 0; }
.swap-y-leave-to { transform: translateY(-60%); opacity: 0; }

.about-section {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(0, 3fr);
  gap: clamp(24px, 4vw, 72px);
  padding-block: clamp(48px, 6vw, 88px);
  border-bottom: 1px solid var(--color-line);
}
.about-label {
  display: flex;
  align-items: baseline;
  gap: 12px;
  align-self: start;
  position: sticky;
  top: calc(var(--header-h) + 32px);
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.about-label span { font-family: var(--font-mono); font-size: 11px; font-weight: 400; color: var(--color-accent); }

.about-intro { max-width: 36em; font-family: var(--font-serif); font-size: clamp(17px, 1.35vw, 19px); line-height: 1.95; color: var(--color-ink-muted); }
.about-intro p + p { margin-top: 1.2em; }
.about-lead {
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 600;
  line-height: 1.6;
  letter-spacing: -0.01em;
  color: var(--color-ink);
}

/* ---- 周期表 ---- */
.periodic { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.element {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 228px;
  padding: 16px 18px 18px;
  outline: none;
  transition: background-color 500ms var(--ease-out-quart), color 500ms var(--ease-out-quart);
}
.element-top {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--color-ink-faint);
  transition: color 500ms var(--ease-out-quart);
}
.element-symbol {
  margin-top: auto;
  font-size: clamp(44px, 4.4vw, 64px);
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.04em;
  font-variation-settings: "opsz" 144, "SOFT" 50;
  transition: transform 700ms var(--ease-spring), color 500ms var(--ease-out-quart);
  transform-origin: 0 100%;
}
.element-name { margin-top: 10px; font-size: 14px; font-weight: 600; }
.element-desc {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-ink-muted);
  transition: color 500ms var(--ease-out-quart);
}
.element-cat {
  position: absolute;
  right: 18px;
  bottom: 18px;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-ink-faint);
  writing-mode: vertical-rl;
  transition: color 500ms var(--ease-out-quart);
}
/* 悬停 / 聚焦：整格反相，符号轻轻放大 */
.element:hover,
.element:focus-visible { background: var(--color-ink); color: var(--color-bg); }
.element:hover .element-symbol,
.element:focus-visible .element-symbol { color: var(--color-accent); transform: scale(1.06); }
.element:hover .element-top,
.element:hover .element-desc,
.element:hover .element-cat,
.element:focus-visible .element-top,
.element:focus-visible .element-desc,
.element:focus-visible .element-cat { color: color-mix(in oklab, var(--color-bg) 60%, transparent); }
.periodic-note { margin-top: 14px; font-size: 12px; color: var(--color-ink-faint); }

/* ---- 经历 ---- */
.trajectory { list-style: none; border-top: 1px solid var(--color-ink); }
.trajectory-item {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 24px;
  padding-block: 24px;
  border-bottom: 1px solid var(--color-line);
}
.trajectory-year {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-accent);
  font-variant-numeric: tabular-nums;
  padding-top: 4px;
}
.trajectory-role { font-family: var(--font-serif); font-size: clamp(18px, 1.6vw, 22px); font-weight: 700; line-height: 1.4; }
.trajectory-desc { margin-top: 6px; font-family: var(--font-serif); font-size: 15px; line-height: 1.8; color: var(--color-ink-muted); }

@media (max-width: 860px) {
  .about-section { grid-template-columns: 1fr; gap: 20px; }
  .about-label { position: static; }
  .periodic { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .trajectory-item { grid-template-columns: 1fr; gap: 6px; }
}
</style>
