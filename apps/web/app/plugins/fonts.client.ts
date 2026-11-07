/**
 * 中文字体切片（思源宋体 / 思源黑体，各约 100 个 unicode-range 切片）的 @font-face 描述本身约 200 KB，
 * 放进首屏关键 CSS 会阻塞渲染。这里在入口脚本执行时立即动态引入：浏览器只下载页面真正用到的切片，
 * 首屏期间中文先以度量对齐过的系统宋体显示（fonts.css 中的 "Serif SC Fallback"），不产生布局跳动。
 */
export default defineNuxtPlugin({
  name: 'fonts',
  enforce: 'pre',
  setup() {
    import('~/styles/fonts-cjk.css');
  },
});
