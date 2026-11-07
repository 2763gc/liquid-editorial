/**
 * 页面的安全响应头。API 的响应头由 FastAPI 自己设置（代理时原样带回）。
 *
 * CSP 的取舍：Nuxt 在页面里内联了启动脚本（运行时配置、四时光照的首帧主题），
 * 没有 nonce 支持时 script-src 只能保留 'unsafe-inline'；其余来源全部收紧：
 * 不允许任何外站脚本、插件、<base> 改写、表单外发，后台页面禁止被嵌入。
 */
const isDev = import.meta.dev;

function csp(admin: boolean, https: boolean) {
  const directives: Record<string, string> = {
    'default-src': "'self'",
    'script-src': `'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ''}`,
    // 霞鹜文楷屏幕阅读版的样式与字体来自 jsDelivr（文章字体主题可选）
    'style-src': "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    'font-src': "'self' data: https://cdn.jsdelivr.net",
    // 文章插图、评论头像、友链图标可能来自任意 https 图床
    'img-src': "'self' data: blob: https:",
    'media-src': "'self' blob: https:",
    'connect-src': `'self'${isDev ? ' ws: wss:' : ''}`,
    'frame-src': "'self' https:",
    'worker-src': "'self' blob:",
    'manifest-src': "'self'",
    'object-src': "'none'",
    'base-uri': "'self'",
    'form-action': "'self'",
    'frame-ancestors': admin ? "'none'" : "'self'",
  };
  const parts = Object.entries(directives).map(([k, v]) => `${k} ${v}`);
  // 只在 https 下要求升级：用 http 预览生产构建时，同源资源被升级成 https 会全部加载失败
  if (https) parts.push('upgrade-insecure-requests');
  return parts.join('; ');
}

export default defineEventHandler((event) => {
  const path = event.path;
  // 代理给 API 的请求、Nitro 自己的接口不在这里处理
  if (path.startsWith('/api/') || path.startsWith('/media-dev/') || path.startsWith('/_nuxt/') || path.startsWith('/__nuxt')) return;
  const admin = path === '/admin' || path.startsWith('/admin/') || path.startsWith('/admin?');
  const https = getRequestProtocol(event, { xForwardedProto: true }) === 'https';
  setResponseHeaders(event, {
    'Content-Security-Policy': csp(admin, https),
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'X-Frame-Options': admin ? 'DENY' : 'SAMEORIGIN',
    'Cross-Origin-Opener-Policy': 'same-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()',
    ...(admin ? { 'Cache-Control': 'no-store' } : {}),
    ...(https && !isDev ? { 'Strict-Transport-Security': 'max-age=31536000; includeSubDomains' } : {}),
  });
});
