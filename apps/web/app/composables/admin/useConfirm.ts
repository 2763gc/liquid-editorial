import { reactive } from 'vue';

/** 后台确认对话框（全局单例），替代原生 confirm()，返回 Promise<boolean> */
export interface ConfirmOptions {
  title: string;
  message?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
}

const state = reactive<{ open: boolean; opts: ConfirmOptions; resolve: ((v: boolean) => void) | null }>({
  open: false,
  opts: { title: '' },
  resolve: null,
});

function confirm(opts: ConfirmOptions): Promise<boolean> {
  state.resolve?.(false);
  return new Promise((resolve) => {
    state.opts = opts;
    state.resolve = resolve;
    state.open = true;
  });
}

function settle(value: boolean) {
  state.resolve?.(value);
  state.resolve = null;
  state.open = false;
}

export function useConfirm() {
  return { state, confirm, settle };
}
