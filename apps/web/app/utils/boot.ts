import { computeLight } from './light';

/**
 * 首屏前执行的内联脚本（写在 <head>，早于任何渲染）：
 * - 主题：自动 / 昼 / 夜；后台使用独立的明暗偏好（默认夜间）
 * - 四时光照 2.0：时段、相邻时段混合比例、窗光角度与色温
 * - 首次加载时颜色在 2 秒内缓动到当前时段（PRD 2.2）：先以「昼」上屏，首帧后再写入真实光照
 * - 设备档位：hardwareConcurrency / deviceMemory / saveData / 指针类型，运行时再按首帧耗时修正
 * - 减弱动效、开场序幕是否已播放、js 标记（CSS 据此决定开场遮罩是否出现，禁用 JS 时不出现）
 * 这些都只写 <html> 的属性与类，Vue 不接管 <html>，不会产生 hydration 不一致。
 */
export function bootScript() {
  return `(function(){try{
var computeLight=${computeLight.toString()};
var d=document.documentElement,n=navigator,now=new Date();
var L=computeLight(now.getHours()*60+now.getMinutes());
var m=localStorage.getItem('blog_theme');if(m!=='light'&&m!=='dark')m='auto';
var adm=location.pathname.indexOf('/admin')===0;
var theme=adm?(localStorage.getItem('blog_admin_theme')==='light'?'light':'dark'):m==='auto'?(L.period==='night'?'dark':'light'):m;
d.setAttribute('data-mode',m);d.setAttribute('data-theme',theme);
var c=n.hardwareConcurrency||4,mem=n.deviceMemory||4,sd=n.connection&&n.connection.saveData,coarse=matchMedia('(pointer: coarse)').matches;
var sc=(c>=8?2:c>=4?1:0)+(mem>=8?2:mem>=4?1:0)-(coarse?1:0);
var tier=sd?'low':sc>=3?'high':sc>=1?'mid':'low';
d.setAttribute('data-tier',tier);d.setAttribute('data-pointer',coarse?'coarse':'fine');
var rm=localStorage.getItem('blog_reduce_motion')==='1'||matchMedia('(prefers-reduced-motion: reduce)').matches;
d.classList.add(rm?'reduce-motion':'motion-ready');
function put(s){d.setAttribute('data-period',s.period);if(s.blend)d.setAttribute('data-blend',s.blend);else d.removeAttribute('data-blend');
d.style.setProperty('--light-t',String(s.t));d.style.setProperty('--light-angle',s.angle+'deg');d.style.setProperty('--light-warmth',String(s.warmth));}
var ease=!adm&&!rm&&tier!=='low'&&theme==='light'&&(L.period!=='day'||L.blend);
if(ease){put({period:'day',blend:'',t:0,angle:180,warmth:0});requestAnimationFrame(function(){requestAnimationFrame(function(){d.classList.add('light-easing');put(L);setTimeout(function(){d.classList.remove('light-easing')},2200);});});}
else put(L);
if(sessionStorage.getItem('seen_curtain')||rm||adm)d.classList.add('curtain-seen');
d.classList.add('js');
}catch(e){document.documentElement.classList.add('js','curtain-seen');}})();`;
}
