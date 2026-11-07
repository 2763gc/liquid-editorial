/**
 * 编辑器的本地草稿与修订（IndexedDB）
 * - 每次改动（防抖）写一份「当前草稿」：断电、关错标签页、接口挂掉都不会丢稿
 * - 每隔两分钟、以及每次成功保存时留一版修订，最多 30 版，可随时回到任意一版
 * - key 是文章 id；新建文章用 'new'，保存成功后迁到真实 id
 */
export interface DraftPayload {
  title: string;
  subtitle: string;
  slug?: string;
  content_md: string;
  layout_variant: string;
  accent_color: string;
  tag_ids: number[];
  is_featured: boolean;
  is_pinned: boolean;
}

export interface Revision {
  at: number;
  /** 'auto' 定时快照；'save' 保存到服务器时的版本；'restore' 恢复前的版本 */
  kind: 'auto' | 'save' | 'restore';
  words: number;
  payload: DraftPayload;
}

interface DraftRecord {
  key: string;
  savedAt: number;
  payload: DraftPayload;
  revisions: Revision[];
}

const DB = 'blog-editor';
const STORE = 'drafts';
const MAX_REVISIONS = 30;
let dbPromise: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: 'key' });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(req ? (req as IDBRequest<T>).result : undefined);
    t.onerror = () => reject(t.error);
  });
}

export function wordsOf(md: string) {
  return (md.match(/[一-龥]/g) || []).length + (md.match(/\b[a-zA-Z]+\b/g) || []).length;
}

export function useDraftStore() {
  const available = typeof indexedDB !== 'undefined';

  async function get(key: string): Promise<DraftRecord | undefined> {
    if (!available) return undefined;
    try {
      return await tx<DraftRecord>('readonly', (s) => s.get(key));
    } catch {
      return undefined;
    }
  }

  async function put(record: DraftRecord) {
    if (!available) return;
    try {
      await tx('readwrite', (s) => s.put(JSON.parse(JSON.stringify(record))));
    } catch {}
  }

  /** 写当前草稿；需要时顺带留一版修订 */
  async function saveDraft(key: string, payload: DraftPayload, revision?: Revision['kind']) {
    const rec = (await get(key)) || { key, savedAt: 0, payload, revisions: [] };
    rec.payload = payload;
    rec.savedAt = Date.now();
    if (revision) {
      const last = rec.revisions[0];
      const same = last && JSON.stringify(last.payload) === JSON.stringify(payload);
      if (!same) {
        rec.revisions.unshift({ at: rec.savedAt, kind: revision, words: wordsOf(payload.content_md), payload });
        rec.revisions = rec.revisions.slice(0, MAX_REVISIONS);
      }
    }
    await put(rec);
    return rec;
  }

  async function revisions(key: string) {
    return (await get(key))?.revisions || [];
  }

  /** 新建文章保存后：把 'new' 下的草稿与修订搬到真实 id */
  async function move(from: string, to: string) {
    const rec = await get(from);
    if (!rec || !available) return;
    rec.key = to;
    await put(rec);
    try { await tx('readwrite', (s) => s.delete(from)); } catch {}
  }

  async function clear(key: string) {
    if (!available) return;
    try { await tx('readwrite', (s) => s.delete(key)); } catch {}
  }

  return { available, get, saveDraft, revisions, move, clear };
}
