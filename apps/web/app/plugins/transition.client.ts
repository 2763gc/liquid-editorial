import gsap from 'gsap';
import { useTransitionStore } from '~/stores/transition';
import { useLenis } from '~/composables/useLenis';
import { prefetchRoute } from '~/utils/prefetch';
import { MOTION } from '~/composables/motion/tokens';

/**
 * 路由切换：不做转场动画，新页面一就绪就直接换上（docs/design-v2.md §4）
 * 这里只负责切换前后的「看不见的」工作：
 * - 悬停链接 100ms 后预取目标页数据，点下去时多半已经到手
 * - 滚动：离开时记下位置；前进回到顶部，后退 / 前进恢复原位，并与 Lenis 同步
 * - 焦点：新页面焦点落到 h1（读屏器播报）；返回时焦点回到原来点击的链接
 * - 换一张纸：纤维贴图跳到新位置；文章页的纸纹更淡
 */
export default defineNuxtPlugin((nuxtApp) => {
  const router = useRouter();
  const store = useTransitionStore(nuxtApp.$pinia as never);
  const root = document.documentElement;
  let popstate = false;
  /** 首次进入（SSR 渲染）也会触发 page:finish；那一次不复位滚动、不抢焦点 */
  let navigated = false;

  history.scrollRestoration = 'manual';
  // 后退 / 前进：挂在 vue-router 的历史对象上。它的监听在 popstate 回调里同步执行，早于导航守卫；
  // 直接监听 window 的 popstate 会排在路由之后，守卫跑完了才记上「这是后退」
  router.options.history.listen(() => { popstate = true; });

  /* ---- 记录点击来源：返回时把焦点还给它 ---- */
  document.addEventListener('click', (e) => {
    const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
    if (!a || e.defaultPrevented || a.target === '_blank' || a.origin !== location.origin) return;
    store.lastClicked[location.pathname] = a.getAttribute('href') || '';
  }, true);

  /* ---- 悬停 100ms 预取 ---- */
  let hoverTimer = 0;
  document.addEventListener('pointerover', (e) => {
    const a = (e.target as Element | null)?.closest?.('a[href^="/"]') as HTMLAnchorElement | null;
    window.clearTimeout(hoverTimer);
    if (!a) return;
    hoverTimer = window.setTimeout(() => prefetchRoute(a.getAttribute('href') || ''), MOTION.prefetchDelay);
  }, { passive: true });

  router.beforeEach((to, from) => {
    if (!from.matched.length || to.path === from.path) return;
    store.saveScroll(from.fullPath, window.scrollY);
    store.popstate = popstate;
    popstate = false;
    prefetchRoute(to.fullPath);
  });

  router.afterEach((to, from, failure) => {
    if (!failure && from.matched.length && to.path !== from.path) navigated = true;
  });

  nuxtApp.hook('page:finish', () => {
    if (!navigated) return;
    navigated = false;
    const to = router.currentRoute.value;
    const y = store.popstate ? store.scroll[to.fullPath] ?? 0 : 0;
    const lenis = useLenis().getLenis();
    if (lenis) lenis.scrollTo(y, { immediate: true, force: true });
    window.scrollTo(0, y);
    if (location.hash) {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) useLenis().scrollTo(el, { immediate: true, offset: -96 });
    }
    root.classList.toggle('is-reading', to.path.startsWith('/posts/'));
    root.style.setProperty('--fiber-x', `${Math.round(Math.random() * 160)}px`);
    root.style.setProperty('--fiber-y', `${Math.round(Math.random() * 160)}px`);

    // 等新页面完成这一帧布局再交焦点
    gsap.ticker.add(function once() {
      gsap.ticker.remove(once);
      const back = store.popstate ? store.lastClicked[to.path] : '';
      const link = back ? document.querySelector<HTMLElement>(`main a[href="${CSS.escape(back)}"]`) : null;
      const h1 = document.querySelector<HTMLElement>('main h1');
      const target = link || h1;
      if (!target) return;
      if (target === h1 && !h1.hasAttribute('tabindex')) h1.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
    });
  });
});
