import { ref, reactive, computed } from 'vue';

/**
 * 后台命令面板的数据源（全局单例）
 * 各处按 owner 注册自己的命令（布局注册「前往 / 动作」，编辑器注册「保存 / 发布」……），卸载时注销。
 * 面板另外按输入实时检索特稿标题（见 AdminCommandPalette）。
 */
export interface AdminCommand {
  id: string;
  group: string;
  label: string;
  hint?: string;
  keywords?: string;
  run: () => unknown;
}

const open = ref(false);
const sources = reactive(new Map<string, AdminCommand[]>());

export function useAdminCommands() {
  return {
    open,
    all: computed(() => [...sources.values()].flat()),
    toggle(next?: boolean) {
      open.value = next ?? !open.value;
    },
    register(owner: string, list: AdminCommand[]) {
      sources.set(owner, list);
    },
    unregister(owner: string) {
      sources.delete(owner);
    },
  };
}
