import { defineConfig, presetUno } from 'unocss';

export default defineConfig({
  presets: [presetUno()],
  theme: {
    colors: {
      accent: 'var(--color-accent)',
      bg: 'var(--color-bg)',
      surface: 'var(--color-surface)',
      ink: 'var(--color-ink)',
      'ink-muted': 'var(--color-ink-muted)',
      'ink-faint': 'var(--color-ink-faint)',
      line: 'var(--color-line)',
    },
    // 让 font-serif / font-sans / font-mono 指向设计 Token，而不是 UnoCSS 默认的 Georgia 等
    fontFamily: {
      display: 'var(--font-display)',
      serif: 'var(--font-serif)',
      sans: 'var(--font-sans)',
      mono: 'var(--font-mono)',
    },
  },
});
