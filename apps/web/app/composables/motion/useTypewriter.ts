import { onMounted, onBeforeUnmount, type Ref } from 'vue';
import gsap from 'gsap';

/**
 * 终端打字：条目第一次进入视口时，命令按真实的打字节奏一个字一个字敲出来，回车后结果才出现。
 * - 节奏：每字 28–70ms，空格与连字符后多停一下，像手在找下一个键
 * - 只在本会话第一次看到时播放；点击条目或按任意键立即补完
 * - 减弱动效：直接显示全文。服务端渲染的是全文，禁用 JS 时照常可读
 * scope 内的每个 [data-type] 元素是一条命令；它最近的 [data-type-entry] 祖先在敲完前带 .is-typing
 */
const SEEN_KEY = 'blog_typed';

export function useTypewriter(scope: Ref<HTMLElement | null>) {
  let io: IntersectionObserver | null = null;
  const running = new Set<() => void>();
  let seen = new Set<string>();

  function finishAll() {
    running.forEach((fn) => fn());
  }

  function type(el: HTMLElement) {
    const entry = el.closest<HTMLElement>('[data-type-entry]');
    const full = el.dataset.type || '';
    const id = el.dataset.typeId || full;
    let i = 0;
    let wait = 0;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      gsap.ticker.remove(step);
      running.delete(finish);
      el.textContent = full;
      entry?.classList.remove('is-typing');
      entry?.classList.add('is-typed');
      seen.add(id);
      try { sessionStorage.setItem(SEEN_KEY, JSON.stringify([...seen])); } catch {}
    };
    const step = (_t: number, dt: number) => {
      wait -= dt;
      if (wait > 0) return;
      i += 1;
      el.textContent = full.slice(0, i);
      const ch = full[i - 1];
      wait = 28 + Math.random() * 42 + (ch === ' ' || ch === '-' ? 70 : 0);
      if (i >= full.length) {
        // 回车前停顿一下
        gsap.delayedCall(0.18, finish);
        gsap.ticker.remove(step);
      }
    };
    running.add(finish);
    entry?.addEventListener('click', finish, { once: true });
    gsap.ticker.add(step);
  }

  function onKey() { finishAll(); }

  onMounted(() => {
    const root = scope.value;
    if (!root || document.documentElement.classList.contains('reduce-motion')) return;
    try { seen = new Set(JSON.parse(sessionStorage.getItem(SEEN_KEY) || '[]')); } catch {}
    io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        io?.unobserve(e.target);
        type(e.target as HTMLElement);
      }
    }, { rootMargin: '0px 0px -12% 0px' });
    root.querySelectorAll<HTMLElement>('[data-type]').forEach((el) => {
      const id = el.dataset.typeId || el.dataset.type || '';
      if (seen.has(id)) return;
      el.textContent = '';
      el.closest('[data-type-entry]')?.classList.add('is-typing');
      io!.observe(el);
    });
    window.addEventListener('keydown', onKey);
  });

  onBeforeUnmount(() => {
    io?.disconnect();
    finishAll();
    window.removeEventListener('keydown', onKey);
  });
}
