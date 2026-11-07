import { defineStore } from 'pinia';

/**
 * 路由切换前后需要记住的东西（plugins/transition.client.ts）
 * - scroll：每个路由离开时的滚动位置，后退 / 前进时恢复
 * - lastClicked：离开某页时点过的链接，返回时把焦点还给它
 * - popstate：本次导航是否来自浏览器的后退 / 前进
 */
export const useTransitionStore = defineStore('transition', {
  state: () => ({
    scroll: {} as Record<string, number>,
    lastClicked: {} as Record<string, string>,
    popstate: false,
  }),
  actions: {
    saveScroll(path: string, y: number) {
      this.scroll[path] = y;
    },
  },
});
