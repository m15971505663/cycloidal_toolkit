"use strict";
/* ============================================================
   摆线针轮减速器 · 原理演示（小红书小工具）
   数学移植自 archive/cycloidal_reduction_demo.html。
   5 阶段分步设计器，上下联动（画布 ↔ 面板）：
     ① 减速比·销布置：只画虚线圆 + 销钉（无摆线），参数 zc / Rp / rp
     ② 摆线生成：参数 e + 「▶ 摆线生成过程预览」滚圆动画
     ③ 啮合修形：参数 drp，静态啮合位看齿面间隙
     ④ W 机构（输出）   ⑤ 运转验证
   画布缩放：mm→px 基础比例仅窗口变化时 fit；调参不重算（销钉视觉恒定）。
            双指捏合 / 滚轮缩放视图（zoom）。
   控制面板：鼠标拖拽 / 触屏滑动 / 滚轮横滚翻页。
   视觉：v7_mobile 浅灰玻璃风。合规：无内联 / 无 fetch / 无 eval。
   ============================================================ */

const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const el = id => document.getElementById(id);

let W = 0, H = 0;

// ---- 设计参数（全放开；直径按用户习惯，内部换算半径）----
const state = { zc: 14, k1: 0.75, Rp: 16, dp: 2, drp: 0.2,
                nw: 6, dw: 2, Rw: 10, eccR: 7, speed: 1, dbl: true };
const FIXED = {};   // 无固定视觉参数（偏心套半径已参数化为 state.eccR）

let phi = 0;            // 输入角（偏心公转，弧度）
let playing = false;

// ---- 阶段（0-4）----
let stageIndex = 0;
const STAGE_SUB = [
  '<b>第 1 步 · 定减速比与销：</b><br>z<sub>c</sub> 决定销钉数，R<sub>p</sub>/d<sub>p</sub> 定销布置',
  '<b>第 2 步 · 生成摆线：</b><br>滚圆滚动画出齿形，偏心 e 定齿形（K₁&lt;1）',
  '<b>第 3 步 · 啮合修形：</b><br>齿廓法向内缩 drp，啮合后齿面与针齿留间隙',
  '<b>第 4 步 · 定 W 机构：</b><br>销数 / 销径 / 分布圆，孔间隙吸收公转',
  '<b>第 5 步 · 运转验证：</b><br>输入转 z<sub>c</sub> 圈 = 输出 1 圈',
];

// ---- 摆线生成动画状态（阶段 ②）----
const genAnim = { playing: false, t: 0 };   // t: 圆→摆线 变形进度 0~1
let drpCur = 0;                              // 当前显示的 drp（阶段切换平滑过渡：②=0，③+=state.drp）
let morphT = 0;                              // 捏合进度：0=②（摆线亮/齿廓淡），1=③+（摆线淡/齿廓亮）
let eccCur = 0;                              // 当前偏心（②=0 居中 → ③=E() 啮合偏心，齿廓向右贴销钉）

// ---- 画布缩放：baseScale = mm→px 基础（fit 一次），zoom = 手势缩放 ----
let baseScale = 1, zoom = 1;
function scale() { return baseScale * zoom; }

// ---- v7 色系 ----
const COLORS = {
  cycloid: '#27ae60',
  cycloidGlow: 'rgba(39,174,96,0.16)',
  pinFill: 'rgba(0,0,0,0.06)', pinStroke: 'rgba(0,0,0,0.28)',
  wPin: '#e67e22', wPinStroke: '#d35400',
  holeStroke: 'rgba(0,0,0,0.30)',
  input: '#4a9eff',
  faint: 'rgba(0,0,0,0.18)',
  label: 'rgba(0,0,0,0.45)',
};

// 偏心距由短幅系数派生：e = K₁·Rp/zp（K₁ 是定曲线类型的无量纲参数）
const E = () => state.k1 * state.Rp / (state.zc + 1);
const P = () => ({ zc: state.zc, zp: state.zc + 1, e: E(), Rp: state.Rp,
                   rp: state.dp / 2, drp: state.drp });   // 内部用半径（直径/2）
const K1 = () => state.k1;                                // 短幅系数即输入值 <1
const K2 = () => state.Rp * Math.sin(Math.PI / (state.zc + 1)) / (state.dp / 2);  // 针径系数 >1

// ---- 齿廓缓存 ----
let dataCache = null, dataKey = '';
function data() {
  const p = P();
  const key = [p.zc, p.e.toFixed(3), p.Rp, p.rp.toFixed(2), p.drp.toFixed(2)].join('|');
  if (key !== dataKey) { dataCache = compute(p); dataKey = key; }
  return dataCache;
}

// ---- 齿廓（Onshape drawCycloid，内圈 sign=+1）----
function compute(p) {
  const N = p.zp * 64, R = p.Rp, n = p.zp, e = p.e;
  const off = p.rp + p.drp;
  const troch = [], tooth = [];
  for (let k = 0; k < N; k++) {
    const t = k / N * 2 * Math.PI;
    const ct = Math.cos(t), st = Math.sin(t);
    const cnt = Math.cos(n * t), snt = Math.sin(n * t);
    const xa = R * ct - e * cnt;
    const ya = R * st - e * snt;
    const dxa = -R * st + n * e * snt;
    const dya = R * ct - n * e * cnt;
    const denom = Math.sqrt(dxa * dxa + dya * dya) || 1;
    const o = off / denom;
    troch.push([xa, ya]);
    tooth.push([xa + o * (-dya), ya + o * dxa]);
  }
  return { troch, tooth };
}

// ---- 位姿：偏心公转（输入）+ 反向自转（输出 = -φ/zc）----
function pose() {
  const e = E();
  return { Cx: e * Math.cos(phi), Cy: e * Math.sin(phi), th: -phi / state.zc };
}

// ---- 阶段视图位姿：1-2 居中设计视图；3 啮合静态；4 静态啮合位；5 运转 ----
function viewPose() {
  if (stageIndex === 4) return pose();                    // ⑤ 运转（偏心公转 + 自转）
  if (stageIndex === 3) return { Cx: E(), Cy: 0, th: 0 }; // ④ 静态啮合位（偏心 +e，不自转）
  return { Cx: eccCur, Cy: 0, th: 0 };                   // ①②居中，③偏心+e（平滑过渡，齿廓向右贴销钉）
}

// ---- 画布适配（仅窗口变化/初始化调用；调参不重算 → 销钉视觉恒定）----
const CY = () => H * 0.40;
function resize() {
  const r = el('viewport').getBoundingClientRect();
  W = Math.max(200, Math.floor(r.width));
  H = Math.max(200, Math.floor(r.height));
  const dpr = window.devicePixelRatio || 1;
  cv.width = Math.floor(W * dpr);
  cv.height = Math.floor(H * dpr);
  cv.style.width = W + 'px';
  cv.style.height = H + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  // 基础比例 fit：默认参数下整个轮（针齿圆 + W 分布圆 + 销）装进画布
  const cy = CY();
  // fit 基准按阶段内容：①②③ 只展示针齿圆 → Rp；④⑤ 有 W 机构 → max(Rp, Rw)
  const base = stageIndex >= 3 ? Math.max(state.Rp, state.Rw) : state.Rp;
  // 激进 fit：默认参数下圆尽量撑满画布（顶部余量 12px，半径外余 4mm）
  // 调参不重算 → 销钉视觉恒定；内容超界用双指/滚轮缩放（zoom 0.35~3.5）看全景
  const avail = Math.min(W / 2 - 40, cy - 12);
  baseScale = Math.max(0.8, avail / (base + state.dp / 2 + 4));
  zoom = 1;
}

function drawPath(pts, close, pp) {
  const c = Math.cos(pp.th), s = Math.sin(pp.th);
  ctx.beginPath();
  pts.forEach((pt, i) => {
    const wx = pt[0] * c - pt[1] * s + pp.Cx;   // 世界 x（自转 + 偏心）
    const wy = pt[0] * s + pt[1] * c + pp.Cy;   // 世界 y
    const xx = sx(wx), yy = sy(wy);             // 屏幕（含聚焦缩放+平移）
    i ? ctx.lineTo(xx, yy) : ctx.moveTo(xx, yy);
  });
  if (close) ctx.closePath();
}

// 针齿/销钉最小视觉半径（像素），防缩太小看不清
const pinRpx = mm => Math.max(mm * vs(), 2.6);

// ---- 按给定偏心距 e 和侧隙 drpVal 计算齿廓点 ----
function computeToothAt(e, drpVal = 0) {
  const R = state.Rp, n = state.zc + 1;
  const off = state.dp / 2 + drpVal;
  const N = n * 64, pts = [];
  for (let k = 0; k < N; k++) {
    const t = k / N * 2 * Math.PI;
    const ct = Math.cos(t), st = Math.sin(t);
    const cnt = Math.cos(n * t), snt = Math.sin(n * t);
    const xa = R * ct - e * cnt;
    const ya = R * st - e * snt;
    const dxa = -R * st + n * e * snt;
    const dya = R * ct - n * e * cnt;
    const denom = Math.sqrt(dxa * dxa + dya * dya) || 1;
    const o = off / denom;
    pts.push([xa + o * (-dya), ya + o * dxa]);
  }
  return pts;
}

// ---- 摆线（trochoid）：滚圆上离圆心 e 的点（针心）的轨迹，"摆线"本义 ----
function computeTrochoid(e) {
  const R = state.Rp, n = state.zc + 1;
  const N = n * 64, pts = [];
  for (let k = 0; k < N; k++) {
    const t = k / N * 2 * Math.PI;
    pts.push([R * Math.cos(t) - e * Math.cos(n * t),
              R * Math.sin(t) - e * Math.sin(n * t)]);
  }
  return pts;
}

// ---- 第二幕聚焦视图（拖 K₁ 放大滚圆，松手恢复）----
const view = { zoom: 1, cx: 0, cy: 0 };
const focus = { t: 0, target: 0 };   // t: 0正常 →1聚焦（平滑过渡）
const FOCUS_ZOOM = 4.5;
function applyFocus() {
  view.zoom = 1 + (FOCUS_ZOOM - 1) * focus.t;
  view.cx = state.Rp * focus.t;      // 聚焦到滚圆（0° 方向世界 (Rp,0)）
  view.cy = 0;
}
const vs = () => scale() * view.zoom;
const sx = wx => W / 2 + (wx - view.cx) * vs();
const sy = wy => CY() - (wy - view.cy) * vs();

// ---- 第二幕：摆线生成（滚圆滚动画出摆线，符合物理）----
function drawStageGen(p) {
  if (genAnim.playing) {
    drawRollAnim(p);
    return;
  }
  const C = COLORS;
  const pinR = pinRpx(p.rp) * view.zoom;

  // 参考圆（针齿中心圆，淡虚线）
  ctx.strokeStyle = C.faint; ctx.lineWidth = 1.4;
  ctx.setLineDash([6, 6]);
  ctx.beginPath(); ctx.arc(sx(0), sy(0), p.Rp * vs(), 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([]);

  // 销钉 ×zp（分布在 Rp 圆上，固定参考）
  for (let i = 0; i < p.zp; i++) {
    const a = i / p.zp * 2 * Math.PI;
    const wx = sx(p.Rp * Math.cos(a)), wy = sy(p.Rp * Math.sin(a));
    ctx.fillStyle = C.pinFill; ctx.strokeStyle = C.pinStroke; ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.arc(wx, wy, pinR, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
  }

  // 摆线（trochoid，亮绿色）——滚圆上黄球（针心=销钉中心）的轨迹
  const pts = computeTrochoid(p.e);
  const trochA = 1 - 0.72 * morphT;   // 摆线不透明度：②亮(1) → ③淡(0.28)
  ctx.beginPath();
  pts.forEach((pt, i) => {
    const wx = sx(pt[0] + eccCur), wy = sy(pt[1]);
    i ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy);
  });
  ctx.closePath();
  ctx.strokeStyle = 'rgba(26,158,80,' + trochA.toFixed(3) + ')';
  ctx.lineWidth = 2.6;
  ctx.stroke();

  // 捏合线（齿廓 tooth，淡绿色）——摆线偏移 rp+drp，阶段③ 捏合上去（透明度替换）
  const tooth = computeToothAt(p.e, drpCur);
  const toothA = 0.28 + 0.72 * morphT;   // 捏合线不透明度：②淡(0.28) → ③亮(1)
  ctx.beginPath();
  tooth.forEach((pt, i) => {
    const wx = sx(pt[0] + eccCur), wy = sy(pt[1]);
    i ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy);
  });
  ctx.closePath();
  ctx.strokeStyle = 'rgba(26,158,80,' + toothA.toFixed(3) + ')';
  ctx.lineWidth = 2.6;
  ctx.stroke();

  // 滚圆（细实线绿色小圆，0° 方向，固定不随偏心）
  const b = p.Rp / p.zp;
  const rcx = sx(p.Rp), rcy = sy(0);
  const rollR = Math.max(b * vs(), 6);
  ctx.strokeStyle = '#1a9e50'; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.arc(rcx, rcy, rollR, 0, 2 * Math.PI); ctx.stroke();

  // 黄球（针心标记，离滚圆圆心 e，在摆线上，固定）+ 连线（长度 = e）
  const tpx = sx(p.Rp - p.e), tpy = sy(0);
  ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(rcx, rcy); ctx.lineTo(tpx, tpy); ctx.stroke();
  ctx.fillStyle = '#f59e0b';
  ctx.beginPath(); ctx.arc(tpx, tpy, 2.4, 0, 2 * Math.PI); ctx.fill();
}

// ---- 滚圆滚动动画（滚圆贴基圆滚，笔尖画出摆线）----
function drawRollAnim(p) {
  const C = COLORS;
  const b = p.Rp / p.zp;               // 滚圆半径
  const Rb = p.Rp - b;                 // 基圆半径
  const fa = genAnim.t * 2 * Math.PI;  // 滚动角 0→2π 滚一圈

  const pinR = pinRpx(p.rp) * view.zoom;

  // 基圆（大虚线圆，滚圆贴它滚）
  ctx.strokeStyle = C.faint; ctx.lineWidth = 1.2;
  ctx.setLineDash([6, 5]);
  ctx.beginPath(); ctx.arc(sx(0), sy(0), Rb * vs(), 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([]);

  // 销钉 ×zp（分布在 Rp 圆上，固定参考）
  for (let i = 0; i < p.zp; i++) {
    const a = i / p.zp * 2 * Math.PI;
    const wx = sx(p.Rp * Math.cos(a)), wy = sy(p.Rp * Math.sin(a));
    ctx.fillStyle = C.pinFill; ctx.strokeStyle = C.pinStroke; ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.arc(wx, wy, pinR, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
  }

  // 摆线（trochoid，滚圆上黄球针心的轨迹）
  const troch = computeTrochoid(p.e);
  const tn = troch.length;
  const idx = Math.min(tn - 1, Math.max(0, Math.round(fa / (2 * Math.PI) * (tn - 1))));

  // 滚圆（细实线绿色小圆，从销钉圆派生 b=Rp/zp，随滚圆滚动）
  const rcx = sx(p.Rp * Math.cos(fa)), rcy = sy(p.Rp * Math.sin(fa));
  const rollR = Math.max(b * vs(), 6);
  ctx.strokeStyle = '#1a9e50'; ctx.lineWidth = 1.2;
  ctx.beginPath(); ctx.arc(rcx, rcy, rollR, 0, 2 * Math.PI); ctx.stroke();

  // 黄球（针心标记，离滚圆圆心 e，随滚圆滚）+ 连线（长度 = e）
  const tpx = sx(p.Rp * Math.cos(fa) - p.e * Math.cos(p.zp * fa));
  const tpy = sy(p.Rp * Math.sin(fa) - p.e * Math.sin(p.zp * fa));
  ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(rcx, rcy); ctx.lineTo(tpx, tpy); ctx.stroke();
  ctx.fillStyle = '#f59e0b';
  ctx.beginPath(); ctx.arc(tpx, tpy, 2.2, 0, 2 * Math.PI); ctx.fill();

  // 黄球画出的摆线（trochoid，亮绿色，0→idx 生长）
  const trochA = 1 - 0.72 * morphT;
  ctx.strokeStyle = 'rgba(26,158,80,' + trochA.toFixed(3) + ')'; ctx.lineWidth = 2.2;
  ctx.beginPath();
  for (let i = 0; i <= idx; i++) {
    const wx = sx(troch[i][0] + eccCur), wy = sy(troch[i][1]);
    i ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy);
  }
  ctx.stroke();

  // 捏合线（齿廓，淡绿色，完整）作为参考
  const toothA = 0.28 + 0.72 * morphT;
  const toothFull = computeToothAt(p.e, drpCur);
  ctx.strokeStyle = 'rgba(26,158,80,' + toothA.toFixed(3) + ')'; ctx.lineWidth = 2.2;
  ctx.beginPath();
  toothFull.forEach((pt, i) => {
    const wx = sx(pt[0] + eccCur), wy = sy(pt[1]);
    i ? ctx.lineTo(wx, wy) : ctx.moveTo(wx, wy);
  });
  ctx.closePath();
  ctx.stroke();
}

// ---- 渲染（随阶段展示不同重点，与面板联动）----
function draw() {
  const p = P();
  const pp = viewPose();
  const cy = CY();
  const s = scale();
  const C = COLORS;
  const S = stageIndex;
  ctx.clearRect(0, 0, W, H);

  // 第二幕（摆线生成）：圆→摆线，聚焦曲线本身
  if (S === 1) {
    drawStageGen(p);
    return;
  }

  // 公转轨迹（阶段 ③+ 啮合位）
  if (S >= 2) {
    const e = E();
    ctx.strokeStyle = C.faint; ctx.lineWidth = 1;
    ctx.setLineDash([3, 4]);
    ctx.beginPath(); ctx.arc(sx(0), sy(0), e * vs(), 0, 2 * Math.PI); ctx.stroke();
    ctx.setLineDash([]);
  }

  // 针齿中心圆（虚线）+ 针齿 ×zp（所有阶段；① 只有虚线 + 销钉）
  ctx.strokeStyle = C.faint;
  ctx.setLineDash([5, 5]);
  ctx.beginPath(); ctx.arc(sx(0), sy(0), p.Rp * vs(), 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([]);
  const pinR = pinRpx(p.rp);
  for (let i = 0; i < p.zp; i++) {
    const a = i / p.zp * 2 * Math.PI;
    const wx = sx(p.Rp * Math.cos(a)), wy = sy(p.Rp * Math.sin(a));
    ctx.fillStyle = C.pinFill; ctx.strokeStyle = C.pinStroke; ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.arc(wx, wy, pinR, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
  }

  // 摆线轮（阶段 ③+ 才画；①② 不画齿廓——①只有销钉，②聚焦曲线）
  if (S >= 2) {
    // 摆线（针心轨迹）只在阶段③ 展示（②生成、③啮合对比）；④+ 删掉辅助线，只留齿廓
    if (S === 2) {
      const trochA = 1 - 0.72 * morphT;
      ctx.strokeStyle = 'rgba(26,158,80,' + trochA.toFixed(3) + ')'; ctx.lineWidth = 2;
      drawPath(data().troch, true, pp); ctx.stroke();
    }
    // 齿廓（tooth）：③ 随 morphT 淡→亮，④+ 全亮
    const toothCur = computeToothAt(p.e, drpCur);
    const toothA = S === 2 ? (0.28 + 0.72 * morphT) : 1;
    // ⑤ 双盘：第二片摆线盘叠装，偏心相差 180°（等效输入角 φ+π）
    // 位姿：中心相反 (−Cx,−Cy)，自转 th − π/zc；淡绿画在下层与主盘区分
    if (S === 4 && state.dbl) {
      const pp2 = { Cx: -pp.Cx, Cy: -pp.Cy, th: pp.th - Math.PI / state.zc };
      ctx.strokeStyle = 'rgba(26,158,80,0.35)'; ctx.lineWidth = 2;
      drawPath(toothCur, true, pp2); ctx.stroke();
    }
    ctx.strokeStyle = 'rgba(26,158,80,' + toothA.toFixed(3) + ')'; ctx.lineWidth = 2;
    drawPath(toothCur, true, pp); ctx.stroke();
  }

  // 偏心套（蓝）：阶段④⑤（W 机构的偏心公转输入），空心描边不要实心
  if (S >= 3) {
    // ⑤ 双盘：第二片盘的偏心（偏心套另一瓣，相差 180°），淡蓝画在下层
    if (S === 4 && state.dbl) {
      const ex2x = W / 2 - pp.Cx * s, ex2y = cy + pp.Cy * s;
      const ecc2px = state.eccR * s;
      ctx.strokeStyle = 'rgba(74,158,255,0.4)'; ctx.lineWidth = 1.4;
      ctx.beginPath(); ctx.arc(ex2x, ex2y, ecc2px, 0, 2 * Math.PI); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(ex2x, ex2y);
      ctx.lineTo(ex2x + ecc2px * Math.cos(phi + Math.PI), ex2y - ecc2px * Math.sin(phi + Math.PI));
      ctx.stroke();
    }
    // 偏心套（输入）：空心小圆 + 快转辐条（蓝），半径 = 偏心套半径 eccR
    const exx = W / 2 + pp.Cx * s, exy = cy - pp.Cy * s;
    const eccRpx = state.eccR * s;
    ctx.strokeStyle = C.input; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(exx, exy, eccRpx, 0, 2 * Math.PI); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(exx, exy);
    ctx.lineTo(exx + eccRpx * Math.cos(phi), exy - eccRpx * Math.sin(phi));
    ctx.stroke();
  }

  // ③ 啮合修形标注：齿廓齿顶 ↔ 销钉左缘的间隙（= drp，内缩量）
  if (S === 2) {
    const toothTip = sx(p.Rp - p.e - p.rp - drpCur + eccCur);  // 齿廓齿顶（0°方向，偏心后）
    const pinLeft = sx(p.Rp - p.rp);                            // 销钉左缘（固定）
    const py = sy(0);
    ctx.strokeStyle = C.label; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(toothTip, py);
    ctx.lineTo(pinLeft, py);
    ctx.stroke();
    ctx.fillStyle = C.label;
    ctx.font = '600 10.5px -apple-system, sans-serif';
    ctx.fillText('drp', (toothTip + pinLeft) / 2 - 10, py - 6);
  }

  // W 机构（阶段 ④+）：孔随盘公转+自转，销只慢转
  if (S >= 3) {
    // ⑤ W 销分布圆（虚线，淡橙与黄销呼应；销绕中心原地慢转，圆心在轴线上不动）
    if (S === 4) {
      ctx.strokeStyle = 'rgba(230,126,34,0.4)'; ctx.lineWidth = 1.2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath(); ctx.arc(W / 2, cy, state.Rw * s, 0, 2 * Math.PI); ctx.stroke();
      ctx.setLineDash([]);
    }
    const wR = state.dw / 2;                       // W 销半径 = 直径/2
    const holeR = (wR + E()) * s;
    // ⑤ 双盘：第二片盘的 W 孔（随盘 2 位姿公转+自转），淡描在下层
    // 孔相位差 +π/zc（= 两盘自转差）：补偿盘 2 的转角错位，
    // 使同一组 W 销同时内切于两片盘的孔（实机两片盘的销孔即这样错位钻出）
    if (S === 4 && state.dbl) {
      const pp2 = { Cx: -pp.Cx, Cy: -pp.Cy, th: pp.th - Math.PI / state.zc };
      ctx.strokeStyle = 'rgba(0,0,0,0.14)'; ctx.lineWidth = 1.1;
      for (let i = 0; i < state.nw; i++) {
        const a = i / state.nw * 2 * Math.PI + pp2.th + Math.PI / state.zc;
        const hx = pp2.Cx + state.Rw * Math.cos(a), hy = pp2.Cy + state.Rw * Math.sin(a);
        ctx.beginPath();
        ctx.arc(W / 2 + hx * s, cy - hy * s, holeR, 0, 2 * Math.PI);
        ctx.stroke();
      }
    }
    ctx.strokeStyle = C.holeStroke; ctx.lineWidth = 1.1;   // 孔只描边，透明不填充
    for (let i = 0; i < state.nw; i++) {
      const a = i / state.nw * 2 * Math.PI + pp.th;
      const hx = pp.Cx + state.Rw * Math.cos(a), hy = pp.Cy + state.Rw * Math.sin(a);
      ctx.beginPath();
      ctx.arc(W / 2 + hx * s, cy - hy * s, holeR, 0, 2 * Math.PI);
      ctx.stroke();
    }
    ctx.fillStyle = C.wPin; ctx.strokeStyle = C.wPinStroke; ctx.lineWidth = 1;
    for (let i = 0; i < state.nw; i++) {
      const a = i / state.nw * 2 * Math.PI + pp.th;
      const px = state.Rw * Math.cos(a), py = state.Rw * Math.sin(a);
      const cpx = W / 2 + px * s, cpy = cy - py * s;
      const r = pinRpx(wR);
      ctx.beginPath(); ctx.arc(cpx, cpy, r, 0, 2 * Math.PI);
      ctx.fill(); ctx.stroke();
      // 销内小箭头（切向，指向输出自转方向；th = −φ/zc 屏幕上为顺时针）
      // 屏幕速度方向 = (sin a, cos a)，短小仅作提示
      const ux = Math.sin(a), uy = Math.cos(a);
      const L = r * 0.85, hd = Math.max(2, r * 0.45);
      const hx = cpx + ux * L, hy = cpy + uy * L;
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(cpx - ux * L, cpy - uy * L); ctx.lineTo(hx, hy);
      ctx.moveTo(hx, hy); ctx.lineTo(hx - ux * hd - uy * hd * 0.85, hy - uy * hd + ux * hd * 0.85);
      ctx.moveTo(hx, hy); ctx.lineTo(hx - ux * hd + uy * hd * 0.85, hy - uy * hd - ux * hd * 0.85);
      ctx.stroke();
      ctx.strokeStyle = C.wPinStroke; ctx.lineWidth = 1;   // 恢复，下一个销描边用
    }
    // 输入轴标记（中心即输入轴线位，连线指向输入角 φ）
    // 输出不加标记：黄色 W 销本身就是输出，其慢速自转直观可见
    ctx.strokeStyle = C.input; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(W / 2, cy, 2.5 * s, 0, 2 * Math.PI); ctx.stroke();
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(W / 2, cy);
    ctx.lineTo(W / 2 + 5 * s * Math.cos(phi), cy - 5 * s * Math.sin(phi)); ctx.stroke();
  }

  // 圈数读数（阶段 ⑤ 运转验证）
  if (S === 4) {
    el('inCnt').innerHTML = (phi / (2 * Math.PI)).toFixed(1) + '<small>圈</small>';
    el('outCnt').innerHTML = (Math.abs(pp.th) / (2 * Math.PI)).toFixed(2) + '<small>圈</small>';
  }
}

// ---- 运转循环 ----
function loop() {
  if (playing && stageIndex === 4) {   // 只有阶段⑤ 运转，阶段④ 静止
    phi += 0.016 * state.speed;
  }
  if (genAnim.playing) {
    genAnim.t += 0.016 / 2.0;                          // 约 2 秒滚一圈
    if (genAnim.t >= 1) {
      genAnim.t = 1;
      genAnim.playing = false;
      el('genBtn').textContent = '▶ 摆线生成过程预览';
    }
  }
  // 聚焦视图平滑过渡（拖 K₁ 放大滚圆 → 松手恢复）
  if (focus.t !== focus.target) {
    focus.t += (focus.target - focus.t) * 0.18;
    if (Math.abs(focus.target - focus.t) < 0.001) focus.t = focus.target;
    applyFocus();
  }
  // ②↔③ 过渡动画：三节点严格镜像
  // 前进：不透明度 → 位移(ecc) → 缩放(drp)
  // 后退：缩放(drp) → 位移(ecc) → 不透明度
  const intoStage3 = stageIndex >= 2;
  if (intoStage3) {
    if (morphT < 0.999) {
      morphT += (1 - morphT) * 0.09;
      if (morphT > 0.999) morphT = 1;
    } else if (Math.abs(eccCur - E()) > 0.0005) {
      const e = E();
      eccCur += (e - eccCur) * 0.08;
      if (Math.abs(e - eccCur) < 0.0005) eccCur = e;
    } else if (Math.abs(drpCur - state.drp) > 0.0005) {
      drpCur += (state.drp - drpCur) * 0.08;
      if (Math.abs(state.drp - drpCur) < 0.0005) drpCur = state.drp;
    }
  } else {
    if (drpCur > 0.0005) {
      drpCur += (0 - drpCur) * 0.08;
      if (drpCur < 0.0005) drpCur = 0;
    } else if (eccCur > 0.0005) {
      eccCur += (0 - eccCur) * 0.08;
      if (eccCur < 0.0005) eccCur = 0;
    } else if (morphT > 0.001) {
      morphT += (0 - morphT) * 0.09;
      if (morphT < 0.001) morphT = 0;
    }
  }
  draw();
  requestAnimationFrame(loop);
}

function setPlaying(v) {
  playing = v;
  el('play').textContent = playing ? '⏸ 暂停' : '▶ 运转';
  el('play').classList.toggle('playing', playing);
}

// ---- 参数联动（不重算画布比例 → 销钉视觉恒定；双指/滚轮缩放视图）----
function applyParams() {
  const e = E(), k2 = K2();
  el('zcV').textContent = state.zc;
  el('zpV').textContent = state.zc + 1;
  el('ratioBadge').textContent = '1 : ' + state.zc;
  el('RpV').innerHTML = state.Rp + '<small>mm</small>';
  el('dpV').innerHTML = state.dp.toFixed(1) + '<small>mm</small>';
  el('k1V').textContent = state.k1.toFixed(2);
  el('eV').innerHTML = e.toFixed(2) + '<small>mm</small>';
  el('drpV').innerHTML = state.drp.toFixed(2) + '<small>mm</small>';
  el('nwV').textContent = state.nw;
  el('dwV').innerHTML = state.dw.toFixed(1) + '<small>mm</small>';
  el('RwV').innerHTML = state.Rw + '<small>mm</small>';
  el('eccRV').innerHTML = state.eccR + '<small>mm</small>';
  el('holeRV').textContent = (state.dw / 2 + e).toFixed(1);
  // K₂ 针径系数（① 销布置）
  el('k2V').textContent = k2.toFixed(2);
  const k2Note = el('k2Note');
  k2Note.textContent = k2 > 1 ? '✓ 针不重叠' : '⚠ 针齿干涉';
  k2Note.className = k2 > 1 ? 'ok' : (k2 > 0.85 ? 'warn' : 'danger');
  draw();
}

// ---- 阶段切换（点击上方圆点；面板横向分屏，程序滚动对齐，无手势）----
const stagesEl = el('stages');
function setStage(i) {
  stageIndex = i;
  document.querySelectorAll('.stage-dot').forEach((d, k) => d.classList.toggle('active', k === i));
  el('stepHint').innerHTML = STAGE_SUB[i];
  // 离开 ② 时停掉生成动画
  if (i !== 1 && genAnim.playing) {
    genAnim.playing = false; genAnim.t = 0;
    el('genBtn').textContent = '▶ 摆线生成过程预览';
  }
  // 切到阶段④（静止）时，停止运转并复位
  if (i === 3) {
    playing = false;
    phi = 0;
    setPlaying(false);
  }
  // 面板横向滚动对齐该阶段（overflow:hidden 下 scrollLeft 仍可程序赋值）
  stagesEl.scrollTo({ left: i * stagesEl.clientWidth, behavior: 'smooth' });
  resize();   // 按阶段内容重 fit（①②③ → Rp；④⑤ → max(Rp,Rw)）
  draw();
}
document.querySelectorAll('.stage-dot').forEach(d => {
  d.addEventListener('click', () => setStage(+d.dataset.i));
});

// ---- 画布双指缩放（触屏捏合）+ 滚轮缩放（PC）----
const ZOOM_MIN = 0.35, ZOOM_MAX = 3.5;
let pinch = null;
function pinchDist(t) {
  return Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
}
cv.addEventListener('touchstart', e => {
  if (e.touches.length === 2) {
    pinch = { d: pinchDist(e.touches), startZoom: zoom };
    e.preventDefault();
  }
}, { passive: false });
cv.addEventListener('touchmove', e => {
  if (pinch && e.touches.length === 2) {
    const d = pinchDist(e.touches);
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, pinch.startZoom * d / pinch.d));
    draw();
    e.preventDefault();
  }
}, { passive: false });
cv.addEventListener('touchend', e => {
  if (e.touches.length < 2) pinch = null;
});
cv.addEventListener('wheel', e => {
  e.preventDefault();
  zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)));
  draw();
}, { passive: false });

// ---- 事件绑定（无行内事件）----
el('play').addEventListener('click', () => setPlaying(!playing));
el('reset').addEventListener('click', () => {
  phi = 0;
  setPlaying(false);
});
el('spd').addEventListener('input', () => {
  state.speed = +el('spd').value;
  el('spdV').textContent = state.speed.toFixed(1);
});
// 双摆线盘开关（⑤：两片叠装，180° 相差）
el('dblDisc').addEventListener('click', () => {
  state.dbl = !state.dbl;
  el('dblDisc').classList.toggle('on', state.dbl);
  draw();
});
el('genBtn').addEventListener('click', () => {
  genAnim.t = 0;
  genAnim.playing = true;
  el('genBtn').textContent = '⏳ 生成中…';
});
['zc', 'dp', 'Rp', 'k1', 'drp', 'dw', 'Rw', 'eccR'].forEach(id => {
  el(id).addEventListener('input', () => {
    state[id] = +el(id).value;
    applyParams();
  });
});
// W 销数 ± 步进器
el('nwMinus').addEventListener('click', () => {
  state.nw = Math.max(4, state.nw - 1);
  applyParams();
});
el('nwPlus').addEventListener('click', () => {
  state.nw = Math.min(12, state.nw + 1);
  applyParams();
});
// 拖 K₁（修偏心距）或 drp（修侧隙）时放大聚焦啮合处，松手恢复
el('k1').addEventListener('pointerdown', () => { focus.target = 1; });
el('drp').addEventListener('pointerdown', () => { focus.target = 1; });
window.addEventListener('pointerup', () => { if (focus.target === 1) focus.target = 0; });
window.addEventListener('resize', () => {
  resize();
  draw();
});

// ---- 长按抑制（安卓 WebView / MIUI 识屏：长按滑块触发系统截图识别）----
// touchstart preventDefault 阻断默认长按链路；滑块拖动改由 pointer 事件手动驱动，
// 值 = 触点位置（按 step 取整），行为与原生一致。桌面鼠标不受影响。
document.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('touchstart', e => e.preventDefault(), { passive: false });  // 画布长按（图片识别菜单）
document.querySelectorAll('input[type="range"]').forEach(inp => {
  inp.addEventListener('touchstart', e => e.preventDefault(), { passive: false });
  const step = +inp.step, min = +inp.min, max = +inp.max;
  const dec = (String(step).split('.')[1] || '').length;
  const setFromX = x => {
    const r = inp.getBoundingClientRect();
    const t = Math.min(1, Math.max(0, (x - r.left) / r.width));
    inp.value = (Math.round((min + t * (max - min)) / step) * step).toFixed(dec);
    inp.dispatchEvent(new Event('input', { bubbles: true }));
  };
  inp.addEventListener('pointerdown', e => {
    setFromX(e.clientX);
    try { inp.setPointerCapture(e.pointerId); } catch (_) {}
  });
  inp.addEventListener('pointermove', e => {
    if (e.buttons && inp.hasPointerCapture(e.pointerId)) setFromX(e.clientX);
  });
});

// ---- 启动 ----
resize();
applyParams();
loop();
