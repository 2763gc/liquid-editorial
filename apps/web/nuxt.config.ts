// https://nuxt.com/docs/api/configuration/nuxt-config
import { bootScript } from './app/utils/boot';
import { motionCss } from './app/composables/motion/tokens';

const API = process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000';

export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  future: {
    compatibilityVersion: 4,
  },
  devtools: { enabled: true },
  modules: ['@pinia/nuxt', '@vueuse/nuxt', '@unocss/nuxt'],
  // 字体先于 Token：fonts.css 只含拉丁子集与回退度量（约 4 KB）；中文切片由 plugins/fonts.client.ts 动态引入
  css: ['~/styles/fonts.css', '~/styles/tokens.css', '~/styles/reset.css', '~/styles/typography.css', '~/styles/components.css', '~/styles/ink.css'],
  routeRules: {
    '/admin/**': { ssr: false, headers: { 'X-Robots-Tag': 'noindex' } },
    '/api/cover/**': { headers: { 'cache-control': 'public, max-age=86400, stale-while-revalidate=604800' } },
  },
  nitro: {
    compressPublicAssets: true,
    routeRules: {
      // /api/v1/** 的反向代理在 server/routes/api/v1/[...path].ts：需要改写 X-Forwarded-For
      // 未配置 COS 时，上传的图片由 API 以 /media-dev 静态目录提供
      '/media-dev/**': { proxy: `${API}/media-dev/**` },
      '/fonts/**': { headers: { 'cache-control': 'public, max-age=31536000, immutable' } },
    },
  },
  typescript: {
    strict: true,
    typeCheck: false,
  },
  app: {
    // 页面之间不做转场；plugins/transition.client.ts 只负责预取、滚动复位与焦点
    pageTransition: false,
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: "Luntrix's Editorial · 空间化个人技术博客",
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
        { name: 'description', content: '以杂志级排版 × 空间化交互 × 电影级动效为核心的软件开发者个人技术博客' },
        { name: 'theme-color', content: '#F2EFE8', media: '(prefers-color-scheme: light)' },
        { name: 'theme-color', content: '#0C0C0D', media: '(prefers-color-scheme: dark)' },
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'alternate', type: 'application/rss+xml', title: 'RSS', href: '/rss.xml' },
        { rel: 'alternate', type: 'application/atom+xml', title: 'Atom', href: '/atom.xml' },
        // 首屏标题字体：稳定 URL，可预加载（ADR 007）
        { rel: 'preload', as: 'font', type: 'font/woff2', href: '/fonts/fraunces-latin-soft-normal.woff2', crossorigin: '' },
      ],
      style: [{ innerHTML: motionCss(), key: 'motion-tokens', tagPriority: 'critical' }],
      script: [{ innerHTML: bootScript(), tagPosition: 'head', tagPriority: 'critical', key: 'boot' }],
    },
  },
});
