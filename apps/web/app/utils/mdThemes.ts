/**
 * Markdown 排版主题（后台编辑器预览与导出共用）
 * 样式见 styles/md-themes.css：每个主题是 .md-paper 上的一个类，全部作用于渲染器输出的真实 HTML。
 */
export interface MdTheme {
  id: string;
  name: string;
  en: string;
  desc: string;
  /** 纸面明暗：决定导出文档的底色与 data-theme */
  tone: 'light' | 'dark';
  /** 代码块配色：light 用 Shiki 亮色、dark 用暗色变量 */
  code: 'light' | 'dark';
  /** 卡片色票：纸色、墨色、强调色 */
  swatch: [string, string, string];
  tags: string[];
  /** 需要按需加载的网络字体 */
  font?: string;
}

const WENKAI = 'https://cdn.jsdelivr.net/npm/lxgw-wenkai-screen-webfont@1.7.0/lxgwwenkaiscreen.css';

export const MD_THEMES: MdTheme[] = [
  { id: 'site', name: '刊物', en: 'Editorial', desc: '与前台文章完全一致的杂志排版', tone: 'light', code: 'light', swatch: ['#F2EFE8', '#141414', '#FF4D2E'], tags: ['站点同款', '衬线'] },
  { id: 'sujian', name: '素笺', en: 'Letter Paper', desc: '双线笺框、朱印眉题、着重号与「」引文', tone: 'light', code: 'light', swatch: ['#F7F1E3', '#2F2A24', '#A8382A'], tags: ['古典', '衬线'] },
  { id: 'chengxin', name: '橙心', en: 'Tangerine', desc: '胶囊标题、圆点序号、Mac 代码窗', tone: 'light', code: 'dark', swatch: ['#FFFFFF', '#3A3A3A', '#FA6E3C'], tags: ['公众号', '活泼'] },
  { id: 'qingci', name: '青瓷', en: 'Celadon', desc: '釉色渐晕、页签式标题、白瓷卡片引文', tone: 'light', code: 'light', swatch: ['#F2F6F3', '#2A3631', '#2F8F74'], tags: ['清雅', '衬线标题'] },
  { id: 'keji', name: '科技蓝', en: 'Blueprint', desc: '蓝图封面、带行号的深色代码、信息提示', tone: 'light', code: 'dark', swatch: ['#FFFFFF', '#1F2328', '#2563EB'], tags: ['技术文档', '行号'] },
  { id: 'jijian', name: '极简', en: 'Swiss', desc: '巨号章节数字、大字引语、黑白红秩序', tone: 'light', code: 'light', swatch: ['#FFFFFF', '#111111', '#E30613'], tags: ['海报感', '无衬线'] },
  { id: 'xueshu', name: '学术', en: 'Academic', desc: '章节编号、三线表、图表题注与 (1) 列表', tone: 'light', code: 'light', swatch: ['#FFFFFF', '#1A1A1A', '#1F3A93'], tags: ['论文', '适合打印'] },
  { id: 'shouzhang', name: '手帐', en: 'Journal', desc: '点阵纸、和纸胶带、便利贴与拍立得', tone: 'light', code: 'light', swatch: ['#FBF8F1', '#3A352E', '#E07A5F'], tags: ['楷体', '手作'], font: WENKAI },
  { id: 'yinghua', name: '樱粉', en: 'Sakura', desc: '对话气泡标题、花瓣符号与圆润边角', tone: 'light', code: 'light', swatch: ['#FFF4F7', '#4A3A41', '#EC6A92'], tags: ['柔和', '可爱'] },
  { id: 'jiguang', name: '极光', en: 'Aurora', desc: '极光晕染、渐变描边卡片与渐变表头', tone: 'light', code: 'dark', swatch: ['#FFFFFF', '#2C2A3A', '#7C4DFF'], tags: ['渐变', '现代'] },
  { id: 'daziji', name: '打字机', en: 'Typewriter', desc: '页边红线、等宽字，保留全部 Markdown 记号', tone: 'light', code: 'dark', swatch: ['#F2ECDF', '#2A2724', '#B4432A'], tags: ['等宽', '复古'] },
  { id: 'moye', name: '墨夜', en: 'Midnight', desc: '星点夜幕、霓虹标题与发光代码区', tone: 'dark', code: 'dark', swatch: ['#0F1117', '#CDD1DA', '#C6A0F6'], tags: ['深色', '护眼'] },
];

export const DEFAULT_MD_THEME = 'site';

export function getMdTheme(id?: string | null): MdTheme {
  return MD_THEMES.find((t) => t.id === id) || MD_THEMES[0];
}

/** 纸面根元素的类名：刊物主题复用前台的 .article-prose，其余主题走 .mdt 体系 */
export function mdPaperClass(id: string): string {
  return id === 'site' ? 'md-paper md-site article-prose' : `md-paper mdt mdt-${id}`;
}

/** 按需加载主题字体（只加载一次） */
export function ensureMdThemeFont(theme: MdTheme) {
  if (!theme.font || typeof document === 'undefined') return;
  if (document.querySelector(`link[data-md-font="${theme.id}"]`)) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = theme.font;
  link.dataset.mdFont = theme.id;
  document.head.appendChild(link);
}
