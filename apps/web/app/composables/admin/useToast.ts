import { reactive } from 'vue';

/**
 * 后台轻提示（全局单例）。消失时机由 Toaster 里进度条的 animationend 决定，
 * 因此鼠标悬停时进度暂停，提示也会一起停留。
 */
export type ToastKind = 'success' | 'error' | 'info';

export interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
  duration: number;
}

const toasts = reactive<ToastItem[]>([]);
let seq = 0;

function push(kind: ToastKind, title: string, detail?: string, duration = 3200) {
  const id = ++seq;
  toasts.push({ id, kind, title, detail, duration });
  // 同屏最多 4 条，旧的先走
  while (toasts.length > 4) toasts.shift();
  return id;
}

function dismiss(id: number) {
  const i = toasts.findIndex((t) => t.id === id);
  if (i >= 0) toasts.splice(i, 1);
}

export function useToast() {
  return {
    toasts,
    dismiss,
    success: (title: string, detail?: string) => push('success', title, detail),
    error: (title: string, detail?: string) => push('error', title, detail, 5200),
    info: (title: string, detail?: string) => push('info', title, detail),
  };
}
