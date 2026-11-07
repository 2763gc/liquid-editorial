<script setup lang="ts">
import { computed } from 'vue';
import type { NuxtError } from '#app';

const props = defineProps<{ error: NuxtError }>();

const route = useRoute();
const code = computed(() => props.error?.statusCode || 500);
const isNotFound = computed(() => code.value === 404);
const path = computed(() => (props.error as any)?.url || route.fullPath || '/');

useHead({ title: computed(() => `${code.value} · Luntrix's Editorial`) });

function goHome() {
  clearError({ redirect: '/' });
}
</script>

<template>
  <NuxtLayout>
    <div class="error-page page-shell">
      <div class="error-grid">
        <div class="error-copy">
          <p class="error-kicker"><span>Erratum</span> HTTP {{ code }} · {{ isNotFound ? 'Not Found' : 'Server Error' }}</p>
          <h1 class="error-code font-display" aria-label="错误代码">
            <span v-for="(d, i) in String(code).split('')" :key="i" class="error-digit" :style="{ '--i': i }">{{ d }}</span>
          </h1>
          <p class="error-title">{{ isNotFound ? '这一页没有被印出来。' : '印刷机暂时卡住了。' }}</p>
          <p class="error-desc">
            {{ isNotFound ? '你要找的页面可能已经改版、迁移，或者从未存在。不妨回到首页，或者翻翻文章索引。' : (error.statusMessage || '服务暂时不可用，请稍后刷新重试。') }}
          </p>
          <div class="error-actions">
            <button type="button" class="btn btn-solid" @click="goHome"><span class="btn-arrow is-back" aria-hidden="true">←</span> 返回首页</button>
            <NuxtLink to="/posts" class="btn" @click="clearError()">浏览文章索引</NuxtLink>
          </div>
        </div>

        <figure class="terminal-block error-term" aria-hidden="true">
          <div class="terminal-header">
            <span class="terminal-dots"><i /><i /><i /></span>
            <span>zsh · ~/luntrix</span>
          </div>
          <pre class="terminal-body"><code><span class="term-line"><span class="term-prompt">$</span>cd {{ path }}</span><span class="term-line is-out">{{ isNotFound ? `cd: no such file or directory: ${path}` : `error: upstream responded with ${code}` }}</span><span class="term-line"><span class="term-prompt">$</span>ls ~/</span><span class="term-line is-out">posts/  series/  projects/  til/  archive/</span><span class="term-line"><span class="term-prompt">$</span><span class="term-caret" /></span></code></pre>
        </figure>
      </div>
    </div>
  </NuxtLayout>
</template>

<style scoped>
.error-page { min-height: calc(100svh - var(--header-h) - 160px); display: flex; align-items: center; }
.error-grid {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
  align-items: center;
  gap: clamp(32px, 6vw, 96px);
  padding-block: clamp(48px, 8vw, 120px);
}
.error-kicker {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.error-kicker span { color: var(--color-accent); }
.error-code {
  display: flex;
  margin-top: 12px;
  font-size: clamp(120px, 20vw, 280px);
  font-weight: 800;
  line-height: 0.85;
  letter-spacing: -0.06em;
  font-variation-settings: "opsz" 144, "SOFT" 100, "WONK" 1;
}
.error-digit {
  display: inline-block;
  animation: digit-in 1200ms var(--ease-out-expo) both;
  animation-delay: calc(var(--i) * 90ms + 100ms);
}
.error-digit:nth-child(2) { font-style: italic; font-weight: 300; color: var(--color-accent); }
@keyframes digit-in {
  from { opacity: 0; transform: translate3d(0, 30%, 0) rotate(6deg); filter: blur(8px); }
}
html.reduce-motion .error-digit { animation: none; }
.error-title {
  margin-top: 28px;
  font-family: var(--font-serif);
  font-size: clamp(22px, 2.2vw, 30px);
  font-weight: 900;
}
.error-desc {
  margin-top: 12px;
  max-width: 28em;
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.85;
  color: var(--color-ink-muted);
}
.error-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 32px; }
.error-actions .btn { height: 44px; padding: 0 22px; }

.error-term { margin: 0; box-shadow: var(--shadow-lg); }
.term-caret {
  display: inline-block;
  width: 0.55em;
  height: 1.1em;
  vertical-align: -0.2em;
  background: var(--color-accent);
  animation: caret 1.1s steps(1) infinite;
}
@keyframes caret { 50% { opacity: 0; } }

@media (max-width: 860px) {
  .error-grid { grid-template-columns: 1fr; }
}
</style>
