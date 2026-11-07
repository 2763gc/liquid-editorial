import type { RouterConfig } from '@nuxt/schema';

/**
 * 滚动由 plugins/transition.client.ts 接管：在纸张盖住页面期间复位或恢复，并与 Lenis 同步。
 * 这里不让路由再滚一次，否则转场结束后会出现第二次跳动。
 */
export default <RouterConfig>{
  scrollBehavior: () => false,
};
