<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue';

interface CommentItem {
  id: number;
  author_name: string;
  author_url?: string | null;
  avatar_hash?: string | null;
  content_md: string;
  is_author: boolean;
  created_at: string;
  reply_to?: string | null;
  replies?: CommentItem[];
}

const props = defineProps<{ postSlug: string }>();

const comments = ref<CommentItem[]>([]);
const total = ref(0);
const loading = ref(true);
const loadError = ref(false);

const form = ref({ name: '', email: '', url: '', content: '', trap: '' });
const replyTo = ref<{ id: number; name: string } | null>(null);
const submitting = ref(false);
const notice = ref<{ type: 'ok' | 'error'; text: string } | null>(null);
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const formRef = ref<HTMLElement | null>(null);
const preview = ref(false);

const canSubmit = computed(() => form.value.name.trim().length > 0 && form.value.content.trim().length >= 2 && !submitting.value);

async function load() {
  loading.value = true;
  loadError.value = false;
  try {
    const data = await $fetch<{ items: CommentItem[]; total: number }>(`/api/v1/posts/${encodeURIComponent(props.postSlug)}/comments`);
    comments.value = data.items || [];
    total.value = data.total || 0;
  } catch {
    loadError.value = true;
  } finally {
    loading.value = false;
  }
}

function startReply(c: CommentItem) {
  replyTo.value = { id: c.id, name: c.author_name };
  nextTick(() => {
    formRef.value?.scrollIntoView({ block: 'center', behavior: 'smooth' });
    textareaRef.value?.focus({ preventScroll: true });
  });
}

async function submit() {
  if (!canSubmit.value) return;
  submitting.value = true;
  notice.value = null;
  try {
    const res = await $fetch<{ status: string; message?: string }>(`/api/v1/posts/${encodeURIComponent(props.postSlug)}/comments`, {
      method: 'POST',
      body: {
        author_name: form.value.name.trim(),
        author_email: form.value.email.trim() || undefined,
        author_url: form.value.url.trim() || undefined,
        content_md: form.value.content.trim(),
        parent_id: replyTo.value?.id,
        website_trap: form.value.trap || undefined,
      },
    });
    try {
      localStorage.setItem('comment_author', JSON.stringify({ name: form.value.name, email: form.value.email, url: form.value.url }));
    } catch {}
    form.value.content = '';
    replyTo.value = null;
    preview.value = false;
    notice.value = res.status === 'approved'
      ? { type: 'ok', text: '评论已发布，感谢你的分享。' }
      : { type: 'ok', text: '评论已提交，审核通过后会显示。' };
    await load();
  } catch (err: any) {
    const msg = err?.data?.error?.message || err?.data?.detail || '提交失败，请稍后再试。';
    notice.value = { type: 'error', text: err?.status === 429 ? '评论太频繁了，请稍后再试。' : msg };
  } finally {
    submitting.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit();
}

/* ---- 评论的受限 Markdown：先整体转义，再还原少量语法，杜绝 XSS ---- */
function esc(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}
function renderLite(md: string) {
  const blocks: string[] = [];
  let text = esc(md || '').replace(/```[a-z0-9]*\n?([\s\S]*?)```/gi, (_m, code) => {
    blocks.push(`<pre><code>${code.replace(/\n$/, '')}</code></pre>`);
    return `\u0000${blocks.length - 1}\u0000`;
  });
  text = text
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer nofollow ugc">$1</a>');
  const paragraphs = text.split(/\n{2,}/).map((p) => (p.startsWith('\u0000') ? p : `<p>${p.replace(/\n/g, '<br>')}</p>`));
  return paragraphs.join('').replace(/\u0000(\d+)\u0000/g, (_m, i) => blocks[Number(i)]);
}

function avatar(c: CommentItem) {
  return c.avatar_hash ? `https://cravatar.cn/avatar/${c.avatar_hash}?s=80&d=mp` : '';
}
function initial(name: string) {
  return (name || '?').trim().slice(0, 1).toUpperCase();
}
function safeUrl(url?: string | null) {
  return url && /^https?:\/\//i.test(url) ? url : '';
}
function timeAgo(iso: string) {
  const t = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`;
  return iso.slice(0, 10);
}

onMounted(() => {
  try {
    const saved = JSON.parse(localStorage.getItem('comment_author') || 'null');
    if (saved) Object.assign(form.value, { name: saved.name || '', email: saved.email || '', url: saved.url || '' });
  } catch {}
  load();
});
</script>

<template>
  <section class="comments" aria-labelledby="comments-title">
    <header class="comments-head">
      <h2 id="comments-title" class="comments-title">讨论</h2>
      <span class="comments-count">{{ total }} 条</span>
    </header>

    <form ref="formRef" class="comment-form" novalidate @submit.prevent="submit">
      <div v-if="replyTo" class="reply-bar">
        <span>回复 <strong>@{{ replyTo.name }}</strong></span>
        <button type="button" class="link-draw" @click="replyTo = null">取消</button>
      </div>

      <div class="comment-fields">
        <input v-model="form.name" class="field" type="text" maxlength="50" placeholder="昵称（必填）" aria-label="昵称" autocomplete="nickname">
        <input v-model="form.email" class="field" type="email" placeholder="邮箱（选填，用于头像，不公开）" aria-label="邮箱" autocomplete="email">
        <input v-model="form.url" class="field" type="url" placeholder="网站（选填）" aria-label="网站" autocomplete="url">
      </div>
      <input v-model="form.trap" class="sr-only" type="text" tabindex="-1" autocomplete="off" aria-hidden="true">

      <div class="comment-editor">
        <textarea
          v-show="!preview"
          ref="textareaRef"
          v-model="form.content"
          class="field comment-textarea"
          rows="5"
          maxlength="1000"
          placeholder="说点什么吧。支持 `代码`、**粗体**、[链接](https://) 与 ``` 代码块"
          aria-label="评论内容"
          @keydown="onKeydown"
        />
        <div v-if="preview" class="comment-preview comment-body" v-html="renderLite(form.content) || '<p>（空）</p>'" />
      </div>

      <div class="comment-actions">
        <button type="button" class="link-draw comment-preview-toggle" @click="preview = !preview">{{ preview ? '继续编辑' : '预览' }}</button>
        <span class="comment-hint">{{ form.content.length }}/1000 · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> 发送</span>
        <button type="submit" class="btn btn-solid" :disabled="!canSubmit">{{ submitting ? '发送中…' : '发表评论' }}</button>
      </div>
      <p v-if="notice" class="comment-notice" :class="`is-${notice.type}`" role="status">{{ notice.text }}</p>
    </form>

    <div v-if="loading" class="comments-skeleton" aria-label="加载中">
      <div v-for="i in 2" :key="i" class="sk-row"><span class="sk-avatar" /><span class="sk-lines"><i /><i /></span></div>
    </div>
    <p v-else-if="loadError" class="comments-empty">评论加载失败，<button type="button" class="link-draw" @click="load">重试</button></p>
    <p v-else-if="!comments.length" class="comments-empty">还没有人发言，来留下第一条讨论吧。</p>

    <ol v-else class="comment-list">
      <li v-for="c in comments" :key="c.id" class="comment">
        <div class="comment-avatar" aria-hidden="true">
          <img v-if="avatar(c)" :src="avatar(c)" alt="" loading="lazy">
          <span v-else>{{ initial(c.author_name) }}</span>
        </div>
        <div class="comment-main">
          <div class="comment-meta">
            <a v-if="safeUrl(c.author_url)" :href="safeUrl(c.author_url)" target="_blank" rel="noopener nofollow ugc" class="comment-name link-draw">{{ c.author_name }}</a>
            <span v-else class="comment-name">{{ c.author_name }}</span>
            <span v-if="c.is_author" class="comment-badge">作者</span>
            <time :datetime="c.created_at">{{ timeAgo(c.created_at) }}</time>
            <button type="button" class="comment-reply" @click="startReply(c)">回复</button>
          </div>
          <div class="comment-body" v-html="renderLite(c.content_md)" />

          <ol v-if="c.replies?.length" class="comment-replies">
            <li v-for="r in c.replies" :key="r.id" class="comment is-reply">
              <div class="comment-avatar is-small" aria-hidden="true">
                <img v-if="avatar(r)" :src="avatar(r)" alt="" loading="lazy">
                <span v-else>{{ initial(r.author_name) }}</span>
              </div>
              <div class="comment-main">
                <div class="comment-meta">
                  <span class="comment-name">{{ r.author_name }}</span>
                  <span v-if="r.is_author" class="comment-badge">作者</span>
                  <span v-if="r.reply_to" class="comment-to">回复 @{{ r.reply_to }}</span>
                  <time :datetime="r.created_at">{{ timeAgo(r.created_at) }}</time>
                  <button type="button" class="comment-reply" @click="startReply(r)">回复</button>
                </div>
                <div class="comment-body" v-html="renderLite(r.content_md)" />
              </div>
            </li>
          </ol>
        </div>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.comments { margin-top: clamp(64px, 8vw, 112px); }
.comments-head { display: flex; align-items: baseline; gap: 14px; padding-bottom: 18px; border-bottom: 1px solid var(--color-ink); }
.comments-title { font-family: var(--font-serif); font-size: clamp(26px, 2.6vw, 36px); font-weight: 900; }
.comments-count { font-family: var(--font-mono); font-size: 12px; color: var(--color-ink-muted); }

.comment-form { display: flex; flex-direction: column; gap: 12px; padding-block: 28px; border-bottom: 1px solid var(--color-line); }
.reply-bar {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: var(--fs-small);
  background: color-mix(in oklab, var(--color-accent) 7%, transparent);
  border-left: 2px solid var(--color-accent);
}
.comment-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.comment-textarea { min-height: 132px; }
.comment-preview { min-height: 132px; padding: 12px 14px; border: 1px dashed var(--color-line-strong); }
.comment-actions { display: flex; align-items: center; gap: 16px; }
.comment-preview-toggle { font-size: var(--fs-micro); color: var(--color-ink-muted); }
.comment-hint { margin-left: auto; font-size: 11px; color: var(--color-ink-faint); }
.comment-hint kbd { font-size: 9px; }
.comment-notice { font-size: var(--fs-small); }
.comment-notice.is-ok { color: #10A37F; }
.comment-notice.is-error { color: #E5484D; }

.comments-empty { padding: 48px 0; text-align: center; font-size: var(--fs-small); color: var(--color-ink-muted); }

.comment-list, .comment-replies { list-style: none; }
.comment { display: grid; grid-template-columns: 40px minmax(0, 1fr); gap: 16px; padding-block: 24px; border-bottom: 1px solid var(--color-line); }
.comment.is-reply { grid-template-columns: 28px minmax(0, 1fr); gap: 12px; padding-block: 16px 0; border-bottom: 0; }
.comment-replies { margin-top: 8px; padding-left: 0; border-left: 1px solid var(--color-line); padding-left: 16px; }
.comment-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--color-surface);
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--color-ink-muted);
}
.comment-avatar.is-small { width: 28px; height: 28px; font-size: 13px; }
.comment-avatar img { width: 100%; height: 100%; object-fit: cover; }
.comment-meta { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px; font-size: 12px; color: var(--color-ink-muted); }
.comment-name { font-size: 14px; font-weight: 600; color: var(--color-ink); }
.comment-badge { padding: 1px 6px; font-size: 10px; border-radius: 3px; background: var(--color-accent); color: var(--color-accent-ink); }
.comment-to { color: var(--color-ink-faint); }
.comment-reply { margin-left: auto; font-size: 12px; color: var(--color-ink-muted); opacity: 0; transition: opacity var(--dur-micro) ease, color var(--dur-micro) ease; }
.comment:hover > .comment-main > .comment-meta .comment-reply,
.comment-reply:focus-visible { opacity: 1; }
.comment-reply:hover { color: var(--color-accent); }
@media (hover: none) { .comment-reply { opacity: 1; } }

.comment-body { margin-top: 8px; font-family: var(--font-serif); font-size: 15.5px; line-height: 1.85; overflow-wrap: anywhere; }
.comment-body :deep(p + p), .comment-body :deep(p + pre), .comment-body :deep(pre + p) { margin-top: 0.7em; }
.comment-body :deep(code) { padding: 0.1em 0.35em; font-size: 0.86em; background: color-mix(in oklab, var(--color-ink) 6%, transparent); border-radius: 3px; }
.comment-body :deep(pre) { padding: 12px 14px; overflow-x: auto; background: var(--color-code-bg); border: 1px solid var(--color-line); border-radius: 3px; font-size: 13px; line-height: 1.6; }
.comment-body :deep(pre code) { padding: 0; background: none; }
.comment-body :deep(a) { text-decoration: underline; text-underline-offset: 0.2em; text-decoration-color: color-mix(in oklab, var(--color-accent) 60%, transparent); }

.comments-skeleton { padding-top: 24px; }
.sk-row { display: flex; gap: 16px; padding-block: 16px; }
.sk-avatar { width: 40px; height: 40px; border-radius: 50%; background: var(--color-surface); }
.sk-lines { flex: 1; display: flex; flex-direction: column; gap: 10px; padding-top: 4px; }
.sk-lines i { height: 10px; border-radius: 2px; background: var(--color-surface); }
.sk-lines i:last-child { width: 60%; }

@media (max-width: 720px) {
  .comment-fields { grid-template-columns: 1fr; }
  .comment-hint { display: none; }
  .comment-actions .btn { margin-left: auto; }
}
</style>
