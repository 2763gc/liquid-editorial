<script setup lang="ts">
interface ToolItem {
  name: string;
  verdict: string;
  link?: string;
}

interface ToolCategory {
  title: string;
  en: string;
  subtitle: string;
  items: ToolItem[];
}

const categories: ToolCategory[] = [
  {
    title: '硬件设备',
    en: 'Hardware',
    subtitle: '工欲善其事，必先利其器。打造高专注力的工作站。',
    items: [
      { name: 'MacBook Pro 16" (M3 Max, 64GB)', verdict: '极速编译与超长续航，移动开发与系统分析的主力战机。' },
      { name: 'Dell UltraSharp 32" 4K IPS Black', verdict: '广色域、高对比度与出色的护眼表现，适合长期特稿排版校对。' },
      { name: 'HHKB Professional HYBRID Type-S', verdict: '静电容独有的键程质感与紧凑 Unix 键位，减少手腕移动。' },
      { name: 'Logitech MX Master 3S', verdict: '电磁滚轮与静音微动，多屏跨界流转利器。' },
    ],
  },
  {
    title: '编辑器与环境',
    en: 'Editor',
    subtitle: '排版、编写与重构的视觉中枢。',
    items: [
      { name: 'VS Code + Cursor', verdict: '主力编辑器，结合深度 AI Pair-Programming 与丰富的插件生态。', link: 'https://code.visualstudio.com' },
      { name: 'Vesper / Tokyo Night Theme', verdict: '深邃高对比度暗色主题，长时间编码视觉疲劳极低。' },
      { name: 'Neovim (Lua Config)', verdict: '终端轻量编辑与快速热修复利器，极致轻盈。', link: 'https://neovim.io' },
    ],
  },
  {
    title: '终端与命令行',
    en: 'Terminal',
    subtitle: '高效键指如飞的交互介质。',
    items: [
      { name: 'Ghostty / Warp', verdict: '现代 GPU 加速渲染终端，原生多分屏与极速渲染。' },
      { name: 'Zsh + Starship Prompt', verdict: '极简且信息丰富的跨 Shell 提示符，显示 Git 状态与执行耗时。', link: 'https://starship.rs' },
      { name: 'tmux', verdict: '会话持久化与服务器结对开发必备套件。' },
      { name: 'eza & bat & fzf', verdict: '现代化 Rust 重写套件，替换 ls / cat 与全局模糊查找。' },
    ],
  },
  {
    title: '字体体系',
    en: 'Typefaces',
    subtitle: '排版是阅读的呼吸。精心挑选的等宽与特稿衬线字族。',
    items: [
      { name: 'JetBrains Mono', verdict: '代码主力字体，出色的字重梯队与极具美感的合字 (Ligatures)。' },
      { name: 'Fraunces', verdict: '英文特稿主标题，带有柔和与古怪两条可变轴的老式衬线。' },
      { name: 'Noto Serif SC（思源宋体）', verdict: '中文正文字体，温润如纸的印刷质感。' },
    ],
  },
  {
    title: '服务与基础设施',
    en: 'Infrastructure',
    subtitle: '云端支撑、存储与安全。',
    items: [
      { name: '腾讯云 COS', verdict: '高可用对象存储，配合 STS 临时密钥实现前端安全直传。' },
      { name: 'Docker & Docker Compose', verdict: '容器化编排，保证开发、测试与生产环境强一致。' },
      { name: 'GitHub Actions', verdict: '自动化 CI/CD 流水线与代码质量守护。' },
    ],
  },
];

useHead({
  title: "工具与装备 · Luntrix's Editorial",
  meta: [{ name: 'description', content: '硬件装备、开发环境、终端工具、排版字体与云端服务选型全记录。' }],
});
</script>

<template>
  <div class="uses-page">
    <UiPageMasthead
      index="08"
      en="Gear & Tools"
      label="工具与装备"
      title="工具与装备"
      lede="生产力装备、开发工作流、终端工具与特稿字体配置——日常思考与编码的物理与数字载体。"
    />

    <div class="page-shell">
      <section v-for="(cat, ci) in categories" :key="cat.title" class="uses-section" :aria-labelledby="`uses-${ci}`">
        <header class="uses-head">
          <span class="uses-no">{{ String(ci + 1).padStart(2, '0') }} · {{ cat.en }}</span>
          <h2 :id="`uses-${ci}`" class="uses-title">{{ cat.title }}</h2>
          <p class="uses-sub">{{ cat.subtitle }}</p>
        </header>
        <dl class="uses-list">
          <div v-for="(item, i) in cat.items" :key="item.name" v-reveal="i * 50" class="uses-item reveal">
            <dt class="uses-name">
              <a v-if="item.link" :href="item.link" target="_blank" rel="noopener" class="link-draw">{{ item.name }} <span aria-hidden="true">↗</span></a>
              <template v-else>{{ item.name }}</template>
            </dt>
            <dd class="uses-verdict">{{ item.verdict }}</dd>
          </div>
        </dl>
      </section>

      <!-- Dotfiles -->
      <section class="uses-section" aria-labelledby="uses-dotfiles">
        <header class="uses-head">
          <span class="uses-no">{{ String(categories.length + 1).padStart(2, '0') }} · Dotfiles</span>
          <h2 id="uses-dotfiles" class="uses-title">常用别名</h2>
          <p class="uses-sub">高频命令行加速命令与别名配置。</p>
        </header>
        <figure v-reveal class="terminal-block uses-terminal reveal">
          <div class="terminal-header">
            <span class="terminal-dots"><i /><i /><i /></span>
            <span>~/.zshrc</span>
          </div>
          <pre class="terminal-body"><code><span class="term-line is-out"># 现代 CLI 替换</span><span class="term-line">alias ls="eza --icons --group-directories-first"</span><span class="term-line">alias ll="eza -la --icons --git"</span><span class="term-line">alias cat="bat --paging=never"</span><span class="term-line"> </span><span class="term-line is-out"># Git 效率工作流</span><span class="term-line">alias g="git"</span><span class="term-line">alias gs="git status -sb"</span><span class="term-line">alias gw="git worktree"</span><span class="term-line"> </span><span class="term-line is-out"># 数据库安全热备份与恢复</span><span class="term-line">alias db-backup="python -m app.cli backup"</span><span class="term-line">alias db-restore="python -m app.cli restore"</span></code></pre>
        </figure>
      </section>
    </div>
  </div>
</template>

<style scoped>
.uses-section {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(0, 2.4fr);
  gap: clamp(24px, 4vw, 72px);
  padding-block: clamp(40px, 5vw, 72px);
  border-bottom: 1px solid var(--color-line);
}
.uses-head { align-self: start; position: sticky; top: calc(var(--header-h) + 32px); }
.uses-no {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--color-accent);
}
.uses-title {
  margin-top: 10px;
  font-family: var(--font-serif);
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 900;
  line-height: 1.25;
}
.uses-sub { margin-top: 10px; max-width: 18em; font-size: 13.5px; line-height: 1.75; color: var(--color-ink-muted); }

.uses-list { border-top: 1px solid var(--color-ink); }
.uses-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 24px;
  padding-block: 20px;
  border-bottom: 1px solid var(--color-line);
}
.uses-name { font-size: 15px; font-weight: 600; line-height: 1.55; }
.uses-name span { color: var(--color-accent); font-weight: 400; }
.uses-verdict { font-family: var(--font-serif); font-size: 15px; line-height: 1.8; color: var(--color-ink-muted); }

.uses-terminal { margin: 0; }

@media (max-width: 860px) {
  .uses-section { grid-template-columns: 1fr; gap: 20px; }
  .uses-head { position: static; }
  .uses-item { grid-template-columns: 1fr; gap: 4px; }
}
</style>
