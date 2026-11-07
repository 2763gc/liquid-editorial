import { ensureAdminSession } from '~/composables/admin/useAdminApi';

/**
 * 后台路由守卫：访问令牌只在内存里，页面刷新后先用 HttpOnly Cookie 静默换一枚；
 * 换不到就在渲染前跳去登录页，避免先闪出后台界面再跳转。
 * 已登录时打开登录页，直接回到后台。后台整体 ssr: false，这里只在客户端执行。
 */
export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server || !to.path.startsWith('/admin')) return;
  if (to.path === '/admin/login') {
    if (to.query.reason) return;
    if (await ensureAdminSession()) {
      const target = typeof to.query.redirect === 'string' && to.query.redirect.startsWith('/admin') ? to.query.redirect : '/admin';
      return navigateTo(target, { replace: true });
    }
    return;
  }
  if (!(await ensureAdminSession())) return navigateTo({ path: '/admin/login', query: { redirect: to.fullPath } });
});
