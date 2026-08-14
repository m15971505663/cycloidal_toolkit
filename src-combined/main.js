"use strict";
/* ============================================================
   集成版引导：内摆 + 外摆 同一容器，标题栏分段器切换。
   两个应用各自完整实例（画布/面板/状态独立），隐藏 pane 挂起。
   ============================================================ */

const el = id => document.getElementById(id);

// 长按抑制（全局一次，替代各模块内重复绑定）
document.addEventListener('contextmenu', e => e.preventDefault());

// 实例化两个应用（徽章共享标题栏元素）
const apps = {
  inner: createInnerApp(el('paneInner'), { badge: el('ratioBadge') }),
  outer: createOuterApp(el('paneOuter'), { badge: el('ratioBadge') }),
};

let mode = 'inner';
function setMode(m) {
  mode = m;
  document.body.classList.toggle('mode-inner', m === 'inner');
  document.body.classList.toggle('mode-outer', m === 'outer');
  el('paneInner').classList.toggle('active', m === 'inner');
  el('paneOuter').classList.toggle('active', m === 'outer');
  document.querySelectorAll('.seg-btn').forEach(b => b.classList.toggle('active', b.dataset.m === m));
  el('title').textContent = m === 'inner' ? '内摆线减速器 · 一转就懂' : '外摆线减速器 · 一转就懂';
  // 显示后重 fit + 刷新徽章（隐藏期间可能错过 resize）
  apps[m].resize();
  apps[m].applyParams();
}

document.querySelectorAll('.seg-btn').forEach(b => {
  b.addEventListener('click', () => setMode(b.dataset.m));
});

setMode('inner');
