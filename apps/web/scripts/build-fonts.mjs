/**
 * 生成 app/styles/fonts.css 与 fonts-cjk.css：全站字体自托管（ADR 007）
 * - Fraunces / Inter 的拉丁子集复制到 public/fonts，URL 稳定，首屏可 preload
 * - 其余子集（拉丁扩展、JetBrains Mono、思源宋体 / 黑体 101 个 unicode-range 切片）直接引用 node_modules，由 Vite 打包并加哈希
 * - 思源黑体只用于界面短文本：font-display: optional，首访不阻塞、不跳字，缓存后生效
 * 用法：node scripts/build-fonts.mjs（升级字体包后重跑）
 */
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '..');
const nm = (pkg) => path.join(root, 'node_modules/@fontsource-variable', pkg);
const out = [];
const cjk = [];
let target = out;

function faces(pkg, cssFile, { only, skip, display, publicFiles = [] } = {}) {
  const css = fs.readFileSync(path.join(nm(pkg), cssFile), 'utf8');
  for (const block of css.match(/\/\* [^*]+ \*\/\s*@font-face\s*{[^}]+}/g) || []) {
    const name = block.match(/\/\* ([^*]+) \*\//)[1].trim();
    if (only && !only.some((s) => name.includes(s))) continue;
    if (skip && skip.some((s) => name.includes(s))) continue;
    const file = block.match(/url\(\.\/files\/([^)]+)\)/)[1];
    let url = `../../node_modules/@fontsource-variable/${pkg}/files/${file}`;
    if (publicFiles.includes(file)) {
      fs.copyFileSync(path.join(nm(pkg), 'files', file), path.join(root, 'public/fonts', file));
      url = `/fonts/${file}`;
    }
    let b = block.replace(/url\(\.\/files\/[^)]+\)/, `url(${url})`);
    if (display) b = b.replace(/font-display: \w+;/, `font-display: ${display};`);
    target.push(b);
  }
}

out.push(`/* 本文件由 scripts/build-fonts.mjs 生成，请勿手改 */`);
// Fraunces：wght + opsz + SOFT 轴（WONK 只影响少数斜体字形，不值得多 50% 体积）
faces('fraunces', 'soft.css', { only: ['latin'], publicFiles: ['fraunces-latin-soft-normal.woff2'] });
faces('fraunces', 'soft-italic.css', { only: ['latin'], publicFiles: ['fraunces-latin-soft-italic.woff2'] });
faces('inter', 'wght.css', { only: ['latin'], publicFiles: ['inter-latin-wght-normal.woff2'] });
faces('jetbrains-mono', 'wght.css', { only: ['latin'] });
target = cjk;
cjk.push(`/* 本文件由 scripts/build-fonts.mjs 生成，请勿手改 */`);
faces('noto-serif-sc', 'wght.css', { skip: ['vietnamese', 'cyrillic'] });
faces('noto-sans-sc', 'wght.css', { skip: ['vietnamese', 'cyrillic'], display: 'optional' });

target = out;
// 回退字体度量对齐：字体切换前后行高与字宽一致，消除 CLS
out.push(`
@font-face { font-family: "Fraunces Fallback"; src: local("Georgia"), local("Times New Roman"); size-adjust: 105%; ascent-override: 93%; descent-override: 24%; line-gap-override: 0%; }
@font-face { font-family: "Inter Fallback"; src: local("Arial"), local("Helvetica Neue"), local("Helvetica"); size-adjust: 107.1%; ascent-override: 90.4%; descent-override: 22.5%; line-gap-override: 0%; }
@font-face { font-family: "JetBrains Mono Fallback"; src: local("Consolas"), local("Menlo"), local("Courier New"); size-adjust: 109%; ascent-override: 93%; descent-override: 27%; line-gap-override: 0%; }
@font-face { font-family: "Serif SC Fallback"; src: local("Songti SC"), local("STSong"), local("SimSun"); size-adjust: 100%; ascent-override: 88%; descent-override: 12%; line-gap-override: 0%; }
`);

fs.writeFileSync(path.join(root, 'app/styles/fonts.css'), out.join('\n\n') + '\n');
fs.writeFileSync(path.join(root, 'app/styles/fonts-cjk.css'), cjk.join('\n\n') + '\n');
console.log('fonts.css:', out.length, 'blocks; fonts-cjk.css:', cjk.length, 'blocks');
