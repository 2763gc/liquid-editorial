<script setup lang="ts">
import { ref, shallowRef, watch, onMounted, onBeforeUnmount } from 'vue';
import type { EditorView as EditorViewType } from '@codemirror/view';

/**
 * 正文编辑器：CodeMirror 6，打开编辑器时才按需加载（不进前台任何分包）。
 * - Markdown 语法高亮，围栏代码块按语言着色；配色全部取自站点 Token，随明暗切换
 * - 软换行、行号、当前行、括号配对、搜索（⌘F）、撤销历史
 * - ⌘B 粗体 / ⌘I 斜体 / ⌘K 链接；Tab 缩进两格
 * - 粘贴 / 拖入图片交给父组件上传（emit paste-files）
 * 高度随内容增长，滚动交给外层的写作栏（与预览按比例同步滚动）。
 * 对外暴露 wrap / prefixLines / insert / focus，供工具条调用；光标位置以事件抛出。
 */
const props = defineProps<{ modelValue: string; placeholder?: string }>();
const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void;
  (e: 'caret', pos: { line: number; col: number }): void;
  (e: 'paste-files', files: File[]): void;
  (e: 'ready'): void;
}>();

const host = ref<HTMLElement | null>(null);
const view = shallowRef<EditorViewType | null>(null);
const loading = ref(true);
let applyingExternal = false;

async function create() {
  const [{ EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection, placeholder: ph, dropCursor }, { EditorState }, { defaultKeymap, history, historyKeymap, indentWithTab }, { markdown, markdownLanguage }, { languages }, { syntaxHighlighting, HighlightStyle, bracketMatching, indentOnInput }, { tags }, { search, searchKeymap, highlightSelectionMatches }] = await Promise.all([
    import('@codemirror/view'),
    import('@codemirror/state'),
    import('@codemirror/commands'),
    import('@codemirror/lang-markdown'),
    import('@codemirror/language-data'),
    import('@codemirror/language'),
    import('@lezer/highlight'),
    import('@codemirror/search'),
  ]);

  // 墨色语法高亮：结构用字重与浓淡，强调色只给链接与标题记号
  const ink = HighlightStyle.define([
    { tag: tags.heading, fontWeight: '700', color: 'var(--color-ink)' },
    { tag: tags.heading1, fontSize: '1.28em' },
    { tag: tags.heading2, fontSize: '1.16em' },
    { tag: tags.processingInstruction, color: 'var(--color-accent-text)' },
    { tag: tags.strong, fontWeight: '700' },
    { tag: tags.emphasis, fontStyle: 'italic' },
    { tag: tags.strikethrough, textDecoration: 'line-through' },
    { tag: tags.link, color: 'var(--color-accent-text)', textDecoration: 'underline' },
    { tag: tags.url, color: 'var(--color-ink-faint)' },
    { tag: tags.monospace, fontFamily: 'var(--font-mono)', color: 'var(--color-ink-muted)' },
    { tag: tags.quote, color: 'var(--color-ink-muted)', fontStyle: 'italic' },
    { tag: tags.list, color: 'var(--color-accent-text)' },
    { tag: tags.meta, color: 'var(--color-ink-faint)' },
    { tag: tags.keyword, color: 'var(--color-accent-text)' },
    { tag: [tags.string, tags.special(tags.string)], color: 'var(--color-ok)' },
    { tag: tags.comment, color: 'var(--color-ink-faint)', fontStyle: 'italic' },
    { tag: [tags.number, tags.bool], color: 'var(--color-warn)' },
    { tag: [tags.function(tags.variableName), tags.typeName], color: 'var(--color-info)' },
  ]);

  const theme = EditorView.theme({
    '&': { fontSize: '14.5px', color: 'var(--color-ink)', backgroundColor: 'transparent' },
    '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.9', overflow: 'visible' },
    '.cm-content': { padding: '4px 0 30vh', caretColor: 'var(--color-accent)' },
    '.cm-line': { padding: '0 18px 0 6px' },
    '.cm-gutters': { backgroundColor: 'transparent', border: 'none', color: 'var(--color-ink-faint)', fontSize: '11px' },
    '.cm-lineNumbers .cm-gutterElement': { padding: '0 10px 0 4px', minWidth: '34px' },
    '.cm-activeLine': { backgroundColor: 'color-mix(in oklab, var(--color-ink) 3.5%, transparent)' },
    '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--color-ink)' },
    '&.cm-focused .cm-cursor': { borderLeftColor: 'var(--color-accent)', borderLeftWidth: '2px' },
    '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': { backgroundColor: 'var(--color-selection) !important' },
    '.cm-placeholder': { color: 'var(--color-ink-faint)' },
    '.cm-matchingBracket': { backgroundColor: 'color-mix(in oklab, var(--color-accent) 18%, transparent)', outline: 'none' },
    '.cm-searchMatch': { backgroundColor: 'color-mix(in oklab, var(--color-warn) 30%, transparent)' },
    '.cm-panels': { backgroundColor: 'var(--a-paper)', color: 'var(--color-ink)', borderTop: '1px solid var(--color-line)' },
    '.cm-panels input, .cm-panels button': { fontFamily: 'var(--font-sans)', fontSize: '12px' },
    '&.cm-focused': { outline: 'none' },
  });

  // ⌘B / ⌘I / ⌘K
  const mdKeys = keymap.of([
    { key: 'Mod-b', run: () => (wrap('**'), true) },
    { key: 'Mod-i', run: () => (wrap('*'), true) },
    { key: 'Mod-k', run: () => (wrap('[', '](https://)', '链接文字'), true) },
  ]);

  const state = EditorState.create({
    doc: props.modelValue,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      drawSelection(),
      dropCursor(),
      history(),
      indentOnInput(),
      bracketMatching(),
      highlightSelectionMatches(),
      search({ top: true }),
      EditorState.tabSize.of(2),
      EditorView.lineWrapping,
      markdown({ base: markdownLanguage, codeLanguages: languages }),
      syntaxHighlighting(ink),
      ph(props.placeholder || ''),
      mdKeys,
      keymap.of([indentWithTab, ...defaultKeymap, ...historyKeymap, ...searchKeymap]),
      theme,
      EditorView.updateListener.of((u) => {
        if (u.docChanged && !applyingExternal) emit('update:modelValue', u.state.doc.toString());
        if (u.selectionSet || u.docChanged) {
          const head = u.state.selection.main.head;
          const line = u.state.doc.lineAt(head);
          emit('caret', { line: line.number, col: head - line.from + 1 });
        }
      }),
      EditorView.domEventHandlers({
        paste(e) {
          const files = Array.from(e.clipboardData?.files || []).filter((f) => f.type.startsWith('image/'));
          if (!files.length) return false;
          e.preventDefault();
          emit('paste-files', files);
          return true;
        },
        drop(e, v) {
          const files = Array.from(e.dataTransfer?.files || []).filter((f) => f.type.startsWith('image/'));
          if (!files.length) return false;
          e.preventDefault();
          const pos = v.posAtCoords({ x: e.clientX, y: e.clientY });
          if (pos != null) v.dispatch({ selection: { anchor: pos } });
          emit('paste-files', files);
          return true;
        },
      }),
    ],
  });
  view.value = new EditorView({ state, parent: host.value! });
  loading.value = false;
  emit('ready');
}

/* 外部改动（读取文章、导入文件、恢复修订、上传后替换占位）同步进编辑器 */
watch(() => props.modelValue, (v) => {
  const ed = view.value;
  if (!ed || v === ed.state.doc.toString()) return;
  applyingExternal = true;
  ed.dispatch({ changes: { from: 0, to: ed.state.doc.length, insert: v } });
  applyingExternal = false;
});

function replaceSelection(text: string, selStart = text.length, selEnd = selStart) {
  const ed = view.value;
  if (!ed) return;
  const { from, to } = ed.state.selection.main;
  ed.dispatch({ changes: { from, to, insert: text }, selection: { anchor: from + selStart, head: from + selEnd }, scrollIntoView: true });
  ed.focus();
}

function wrap(before: string, after = before, placeholderText = '文字') {
  const ed = view.value;
  if (!ed) return;
  const { from, to } = ed.state.selection.main;
  const sel = ed.state.sliceDoc(from, to) || placeholderText;
  replaceSelection(before + sel + after, before.length, before.length + sel.length);
}

function prefixLines(prefix: (i: number) => string) {
  const ed = view.value;
  if (!ed) return;
  const { from, to } = ed.state.selection.main;
  const start = ed.state.doc.lineAt(from);
  const end = ed.state.doc.lineAt(to);
  const changes = [];
  for (let n = start.number, i = 0; n <= end.number; n++, i++) changes.push({ from: ed.state.doc.line(n).from, insert: prefix(i) });
  ed.dispatch({ changes });
  ed.focus();
}

function insert(text: string) {
  replaceSelection(text);
}

defineExpose({ wrap, prefixLines, insert, focus: () => view.value?.focus() });

onMounted(create);
onBeforeUnmount(() => view.value?.destroy());
</script>

<template>
  <div class="md-editor" :class="{ 'is-loading': loading }">
    <div ref="host" class="md-editor-host" />
    <div v-if="loading" class="md-editor-proof" aria-hidden="true">
      <span v-for="i in 9" :key="i" class="a-skel" :style="{ width: `${40 + ((i * 37) % 50)}%`, height: '11px', marginTop: '14px' }" />
    </div>
  </div>
</template>

<style scoped>
.md-editor { position: relative; min-height: 60vh; margin-left: -46px; }
.md-editor-proof { position: absolute; inset: 0; padding: 6px 18px 0 46px; }
@media (max-width: 860px) { .md-editor { margin-left: -12px; } }
</style>
