"use strict";
/* ============================================================
   外摆线减速器 · 原理演示（小红书小工具）
   数学移植自 outer/cycloidal_outer_designer.html（sign=−1 hypotrochoid），
   框架复用内摆版（src/main.js）：圆点切换 / pointer 滑条 / 长按抑制 / 双指缩放。
   与内摆的本质差异：
   - SIGN=−1 两处：trochoid 的 x·e 项 + 等距偏移方向（漏一处就不对）
   - 摆线轮是外齿圈包裹针齿；无 W 机构
   - 运动学：摆线轮刚体圆周平动（th=0，中心角=φ），针齿=输出转 −φ/zp
     → 减速比 1:zp（内摆是 1:zc = 1:(zp−1)）
   - 三片叠加 120° 偏心相位（动平衡），齿廓错位 phase/(zp+1)
   3 阶段：① 销布置  ② 摆线齿形  ③ 机构运转
   视觉：v7 浅灰玻璃风 · 紫色主题（内摆为绿）。合规：无内联 / 无 fetch / 无 eval。
   ============================================================ */

const cv = document.getElementById('cv');
const ctx = cv.getContext('2d');
const el = id => document.getElementById(id);

let W = 0, H = 0;

// ---- 设计参数（直径按用户习惯，内部换算半径）----
const state = { zc: 10, dp: 3, Rp: 20, k1: 0.75, drp: 0.2,
                din: 40, capR: 28, speed: 1, stack: true };

const SIGN = -1;        // 外摆核心开关（内摆 +1 / 外摆 −1）

let phi = 0;            // 输入角（胶囊平动相位，弧度）
let playing = false;

// ---- 阶段（0-2）----
let stageIndex = 0;
const STAGE_SUB = [
  '<b>第 1 步 · 定减速比与销：</b><br>z<sub>c</sub> 决定针齿数，减速比 = 1 : z<sub>p</sub>（=z<sub>c</sub>+1）',
  '<b>第 2 步 · 生成摆线：</b><br>滚圆滚动画出外摆齿形（K₁&lt;1），法向偏移得齿廓',
  '<b>第 3 步 · 啮合修形：</b><br>齿廓外胀包裹针齿，偏心 e 卡入，啮合间隙 = drp',
  '<b>第 4 步 · 机构运转：</b><br>胶囊刚体平动输入，针齿被拨慢转输出（1:z<sub>p</sub>）',
];

// ---- 生成动画状态（阶段 ②）----
const genAnim = { playing: false, t: 0 };   // t: 0→1 滚一圈
let meshT = 0;                              // ④ 机构静态啮合位（胶囊视图 memberPose 用）
// ---- ②↔③ 过渡（三节点镜像，同内摆）----
// 前进 ②→③：不透明度(morphT) → 位移(eccCur) → 缩放(drpCur)；后退反序
let morphT = 0;    // 摆线亮 ↔ 齿廓亮 透明度互换
let eccCur = 0;    // 偏心过渡：0 居中 → SIGN·e 啮合位（外摆在 −x 方向）
let drpCur = 0;    // 齿侧间隙过渡：0 → drp（齿廓外胀包针）

// ---- 画布缩放 ----
let baseScale = 1, zoom = 1;
function scale() { return baseScale * zoom; }

// ---- 色系（紫主题；蓝=输入 / 橙=输出，与内摆语义一致）----
const COLORS = {
  member: '#7c3aed',        // 片 1（主紫）
  m2: '#2563eb',            // 片 2（蓝）
  m3: '#059669',            // 片 3（绿）
  pinFill: '#e67e22', pinStroke: '#d35400',   // 针齿=输出（橙）
  input: '#4a9eff',
  faint: 'rgba(0,0,0,0.18)',
  label: 'rgba(0,0,0,0.45)',
};
const TROCH_RGB = '124,58,237';   // 齿廓紫（rgba 前缀）

// ---- 派生参数 ----
const E = () => state.k1 * state.Rp / (state.zc + 1);
const P = () => ({ zc: state.zc, zp: state.zc + 1, e: E(), Rp: state.Rp,
                   rp: state.dp / 2, drp: state.drp });
const K2 = () => state.Rp * Math.sin(Math.PI / (state.zc + 1)) / (state.dp / 2);
const running = () => playing && stageIndex === 3;

// ---- 齿廓（外摆 SIGN=−1 两处：x 的 e 项 + 偏移方向，照 Onshape drawCycloid）----
function computeToothAt(e, drpVal) {
  const R = state.Rp, n = state.zc + 1;
  const off = state.dp / 2 + drpVal;
  const N = n * 64, pts = [];
  for (let k = 0; k < N; k++) {
    const t = k / N * 2 * Math.PI;
    const ct = Math.cos(t), st = Math.sin(t);
    const cnt = Math.cos(n * t), snt = Math.sin(n * t);
    const xa = R * ct - SIGN * e * cnt;            // ← SIGN 只乘 x 的 e 项
    const ya = R * st - e * snt;                   //   y 项恒定
    const dxa = -R * st + SIGN * n * e * snt;
    const dya = R * ct - n * e * cnt;
    const denom = Math.sqrt(dxa * dxa + dya * dya) || 1;
    const o = SIGN * off / denom;                  // ← 偏移方向跟 SIGN（外胀包裹针齿）
    pts.push([xa + o * (-dya), ya + o * dxa]);
  }
  return pts;
}

// ---- 摆线（trochoid，针心轨迹）----
function computeTrochoid(e) {
  const R = state.Rp, n = state.zc + 1;
  const N = n * 64, pts = [];
  for (let k = 0; k < N; k++) {
    const t = k / N * 2 * Math.PI;
    pts.push([R * Math.cos(t) - SIGN * e * Math.cos(n * t),
              R * Math.sin(t) - e * Math.sin(n * t)]);
  }
  return pts;
}

// ---- 位姿：刚体圆周平动（th=0 不自转）。运转：中心角=φ+phase；静止：meshT 渐变 ----
function memberPose(phase) {
  const e = E();
  if (running()) {
    const ang = phi + phase;
    return { Cx: SIGN * e * Math.cos(ang), Cy: SIGN * e * Math.sin(ang), th: 0 };
  }
  return { Cx: SIGN * e * meshT * Math.cos(phase), Cy: SIGN * e * meshT * Math.sin(phase), th: 0 };
}
// 针齿 = 输出：转 −φ/zp（减速比 1:zp）。phi 暂停时停止增长→针齿冻结、计数保留，仅重置归零
const pinAng = p => -phi / p.zp;

// ---- 画布适配 ----
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
  // fit 基准按阶段：①② 只看针齿圆 → Rp；③ 胶囊 + din 机构 → max(capR, din+capR)
  const base = stageIndex === 3
    ? Math.max(state.capR + 2, state.din + state.capR + 2)
    : state.Rp;
  const avail = Math.min(W / 2 - 40, CY() - 12);
  baseScale = Math.max(0.8, avail / (base + state.dp / 2 + 4));
  zoom = 1;
}

// ---- 视图：聚焦缩放（拖 K₁/drp 放大看曲线）+ ③ 机构视点下移 din/2 ----
const view = { zoom: 1, cx: 0, cy: 0 };
const focus = { t: 0, target: 0 };
const FOCUS_ZOOM = 4.5;
function applyFocus() {
  view.zoom = 1 + (FOCUS_ZOOM - 1) * focus.t;
  view.cx = state.Rp * focus.t;
  view.cy = 0;
}
let wOff = 0, wOffT = 0;        // 世界 y 视点偏移：④ 机构中心在 −din/2，居中显示
const vs = () => scale() * view.zoom;
const sx = wx => W / 2 + (wx - view.cx) * vs();
const sy = wy => CY() - (wy - view.cy - wOff) * vs();

const pinRpx = mm => Math.max(mm * vs(), 2.6);
function rgba(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
  return 'rgba(' + r + ',' + g + ',' + b + ',' + a.toFixed(3) + ')';
}

// ---- 针齿（所有阶段；③ 运转时整体慢转 = 输出）----
function drawPins(p, withArrows) {
  const ang = pinAng(p);
  const r = pinRpx(p.rp);
  for (let i = 0; i < p.zp; i++) {
    const a = i / p.zp * 2 * Math.PI + ang;
    const wx = sx(p.Rp * Math.cos(a)), wy = sy(p.Rp * Math.sin(a));
    ctx.fillStyle = COLORS.pinFill; ctx.strokeStyle = COLORS.pinStroke; ctx.lineWidth = 1.1;
    ctx.beginPath(); ctx.arc(wx, wy, r, 0, 2 * Math.PI); ctx.fill(); ctx.stroke();
    if (withArrows) {
      // 切向小箭头（白），指向输出转向（−φ/zp，屏幕顺时针）
      const ux = Math.sin(a), uy = Math.cos(a);
      const L = r * 0.85, hd = Math.max(2, r * 0.45);
      const hx = wx + ux * L, hy = wy + uy * L;
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(wx - ux * L, wy - uy * L); ctx.lineTo(hx, hy);
      ctx.moveTo(hx, hy); ctx.lineTo(hx - ux * hd - uy * hd * 0.85, hy - uy * hd + ux * hd * 0.85);
      ctx.moveTo(hx, hy); ctx.lineTo(hx - ux * hd + uy * hd * 0.85, hy - uy * hd - ux * hd * 0.85);
      ctx.stroke();
      ctx.strokeStyle = COLORS.pinStroke; ctx.lineWidth = 1.1;
    }
  }
}

// ---- 胶囊路径（面板两端圆 A=摆线轮中心 / B=偏心套中心，屏幕坐标）----
function capsulePath(ax, ay, bx, by, r) {
  ctx.moveTo(ax - r, ay);
  ctx.lineTo(bx - r, by);
  ctx.arc(bx, by, r, Math.PI, 0, true);
  ctx.lineTo(ax + r, ay);
  ctx.arc(ax, ay, r, 0, Math.PI, true);
  ctx.closePath();
}

// ---- 一片完整刚体：胶囊(evenodd 挖空) + 摆线轮齿廓 + 偏心圆 ----
// phase：偏心相位（三片 0/120°/240°）；rot = phase/(zp+1) 齿廓错位保证三片都啮合
function drawMember(p, phase, col, alpha) {
  const pose = memberPose(phase);
  const rot = phase / (p.zp + 1);
  const cr = Math.cos(rot), sr = Math.sin(rot);
  const xform = pt => {
    const x0 = pt[0] * cr - pt[1] * sr + pose.Cx;
    const y0 = pt[0] * sr + pt[1] * cr + pose.Cy;
    return [sx(x0), sy(y0)];
  };
  const tooth = computeToothAt(p.e, state.drp);
  const r = state.capR * vs();
  const eccR = 0.3 * p.Rp * vs();
  const ax = sx(pose.Cx), ay = sy(pose.Cy);                    // A=摆线轮中心
  const bx = sx(pose.Cx), by = sy(pose.Cy - state.din);        // B=偏心套中心（同偏移平动）

  // 面板 evenodd：胶囊 ∖ 齿廓内 ∖ 偏心圆内
  ctx.beginPath();
  capsulePath(ax, ay, bx, by, r);
  tooth.forEach((pt, i) => { const w = xform(pt); i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]); });
  ctx.closePath();
  ctx.moveTo(bx + eccR, by); ctx.arc(bx, by, eccR, 0, 2 * Math.PI); ctx.closePath();
  ctx.fillStyle = rgba(col, 0.16 * alpha); ctx.fill('evenodd');

  // 胶囊轮廓
  ctx.beginPath(); capsulePath(ax, ay, bx, by, r);
  ctx.strokeStyle = rgba(col, alpha); ctx.lineWidth = 1.8; ctx.stroke();

  // 齿廓（tooth，亮）——④ 只留齿廓，删辅助摆线（同内摆 ④+）
  ctx.strokeStyle = rgba(col, alpha); ctx.lineWidth = 2.2;
  ctx.beginPath();
  tooth.forEach((pt, i) => { const w = xform(pt); i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]); });
  ctx.closePath(); ctx.stroke();

  // 偏心圆（只轮廓）
  ctx.strokeStyle = rgba(col, alpha * 0.9); ctx.lineWidth = 1.6;
  ctx.beginPath(); ctx.arc(bx, by, eccR, 0, 2 * Math.PI); ctx.stroke();
}

// ---- 阶段 ②：摆线生成动画（滚圆滚出 trochoid）----
function drawGen(p) {
  const C = COLORS;
  // 针齿中心圆（淡虚线）+ 针齿
  ctx.strokeStyle = C.faint; ctx.lineWidth = 1.4;
  ctx.setLineDash([6, 6]);
  ctx.beginPath(); ctx.arc(sx(0), sy(0), p.Rp * vs(), 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([]);
  drawPins(p, false);

  const tr = computeTrochoid(p.e);
  const N = tr.length;
  const idx = Math.min(N - 1, Math.max(0, Math.round(genAnim.t * (N - 1))));
  const t = genAnim.t * 2 * Math.PI;

  if (genAnim.playing) {
    // 滚圆（导圆上滚动，半径 b=Rp/zp）+ 追踪点连线（长度 e）
    const b = p.Rp / p.zp;
    const rcx = sx(p.Rp * Math.cos(t)), rcy = sy(p.Rp * Math.sin(t));
    const rollR = Math.max(b * vs(), 6);
    ctx.strokeStyle = '#7c3aed'; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(rcx, rcy, rollR, 0, 2 * Math.PI); ctx.stroke();
    const tpx = sx(tr[idx][0] + eccCur), tpy = sy(tr[idx][1]);
    ctx.strokeStyle = '#f59e0b'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(rcx, rcy); ctx.lineTo(tpx, tpy); ctx.stroke();
    ctx.fillStyle = '#f59e0b';
    ctx.beginPath(); ctx.arc(tpx, tpy, 2.4, 0, 2 * Math.PI); ctx.fill();
  }

  // 摆线（生长中/完整；②亮 → ③淡）
  const trochA = 1 - 0.72 * morphT;
  ctx.strokeStyle = 'rgba(' + TROCH_RGB + ',' + trochA.toFixed(3) + ')'; ctx.lineWidth = 2.6;
  ctx.beginPath();
  for (let i = 0; i <= (genAnim.playing ? idx : N - 1); i++) {
    const w = [sx(tr[i][0] + eccCur), sy(tr[i][1])];
    i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]);
  }
  ctx.stroke();

  // 齿廓（tooth = trochoid 法向外偏移 rp+drpCur，外摆外胀包裹针齿；②淡 → ③亮）
  const toothA = 0.28 + 0.72 * morphT;
  ctx.strokeStyle = 'rgba(' + TROCH_RGB + ',' + toothA.toFixed(3) + ')'; ctx.lineWidth = 2.2;
  ctx.beginPath();
  computeToothAt(p.e, drpCur).forEach((pt, i) => {
    const w = [sx(pt[0] + eccCur), sy(pt[1])];
    i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]);
  });
  ctx.closePath(); ctx.stroke();
}

// ---- 渲染 ----
function draw() {
  const p = P();
  const S = stageIndex;
  ctx.clearRect(0, 0, W, H);

  // ② 摆线齿形（居中设计视图）
  if (S === 1) { drawGen(p); return; }

  // ①：针齿中心圆（虚线）+ 针齿
  ctx.strokeStyle = COLORS.faint;
  ctx.setLineDash([5, 5]);
  ctx.beginPath(); ctx.arc(sx(0), sy(0), p.Rp * vs(), 0, 2 * Math.PI); ctx.stroke();
  ctx.setLineDash([]);
  drawPins(p, false);

  // ③：啮合视图（齿廓外胀包针 + 偏心 e 卡入 + drp 间隙标注）
  if (S === 2) {
    // A 中心偏心轨迹（淡虚线，随 eccCur 生长）
    if (Math.abs(eccCur) > 0.01) {
      ctx.strokeStyle = COLORS.faint; ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.arc(sx(0), sy(0), Math.abs(eccCur) * vs(), 0, 2 * Math.PI); ctx.stroke();
      ctx.setLineDash([]);
    }
    // 摆线（淡，随 morphT）+ 齿廓（亮）都在 eccCur 偏心位
    const trochA = 1 - 0.72 * morphT;
    ctx.strokeStyle = 'rgba(' + TROCH_RGB + ',' + trochA.toFixed(3) + ')'; ctx.lineWidth = 2;
    ctx.beginPath();
    computeTrochoid(p.e).forEach((pt, i) => {
      const w = [sx(pt[0] + eccCur), sy(pt[1])];
      i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]);
    });
    ctx.closePath(); ctx.stroke();
    const toothW = computeToothAt(p.e, drpCur);
    const toothA = 0.28 + 0.72 * morphT;
    ctx.strokeStyle = 'rgba(' + TROCH_RGB + ',' + toothA.toFixed(3) + ')'; ctx.lineWidth = 2;
    ctx.beginPath();
    toothW.forEach((pt, i) => {
      const w = [sx(pt[0] + eccCur), sy(pt[1])];
      i ? ctx.lineTo(w[0], w[1]) : ctx.moveTo(w[0], w[1]);
    });
    ctx.closePath(); ctx.stroke();
    drawPins(p, false);
    // drp 间隙标注：0° 针齿与最近齿廓点之间（过渡完成后才画）
    if (drpCur > 0.02) {
      const pxw = [p.Rp, 0];                       // 0° 针心（世界）
      let bq = null, bd = 1e9;
      for (const q of toothW) {
        const wx = q[0] + eccCur, wy = q[1];
        const d = Math.hypot(pxw[0] - wx, pxw[1] - wy);
        if (d < bd) { bd = d; bq = [wx, wy]; }
      }
      if (bq && bd > p.rp + 0.01) {                // 有间隙才标
        const ux = (pxw[0] - bq[0]) / bd, uy = (pxw[1] - bq[1]) / bd;
        const x1 = sx(bq[0]), y1 = sy(bq[1]);
        const x2 = sx(pxw[0] - ux * p.rp), y2 = sy(pxw[1] - uy * p.rp);
        ctx.strokeStyle = COLORS.label; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
        ctx.fillStyle = COLORS.label;
        ctx.font = '600 10.5px -apple-system, sans-serif';
        ctx.fillText('drp', (x1 + x2) / 2 - 9, (y1 + y2) / 2 - 6);
      }
    }
  }

  // ④：机构（胶囊刚体 ×1|3 + 针齿输出 + 输入轴）
  if (S === 3) {
    // A 中心公转轨迹（偏心圆，淡虚线）
    const e = E();
    if (meshT > 0.01) {
      ctx.strokeStyle = COLORS.faint; ctx.lineWidth = 1;
      ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.arc(sx(0), sy(0), e * vs(), 0, 2 * Math.PI); ctx.stroke();
      ctx.setLineDash([]);
    }
    // 三片（120° 偏心相位，动平衡）或单片
    if (state.stack) {
      drawMember(p, 4 * Math.PI / 3, COLORS.m3, 0.6);
      drawMember(p, 2 * Math.PI / 3, COLORS.m2, 0.6);
      drawMember(p, 0, COLORS.member, 0.6);
    } else {
      drawMember(p, 0, COLORS.member, 1);
    }
    // 针齿（输出，含转向箭头）画在最上层
    drawPins(p, true);
    // 输入轴心（固定，蓝）+ 壳心 O + 到片1 偏心套中心的偏心方向线
    const pose0 = memberPose(0);
    const oX = sx(0), oY = sy(0);
    const inX = sx(0), inY = sy(-state.din);
    const b0x = sx(pose0.Cx), b0y = sy(pose0.Cy - state.din);
    ctx.fillStyle = '#9ca3af';
    ctx.beginPath(); ctx.arc(oX, oY, 2.5, 0, 2 * Math.PI); ctx.fill();
    ctx.fillStyle = COLORS.input;
    ctx.beginPath(); ctx.arc(inX, inY, Math.max(2.5, 0.12 * p.Rp * vs()), 0, 2 * Math.PI); ctx.fill();
    ctx.strokeStyle = COLORS.input; ctx.lineWidth = 1.4;
    ctx.beginPath(); ctx.moveTo(inX, inY); ctx.lineTo(b0x, b0y); ctx.stroke();
    // 圈数读数
    el('inCnt').innerHTML = (phi / (2 * Math.PI)).toFixed(1) + '<small>圈</small>';
    el('outCnt').innerHTML = (Math.abs(pinAng(p)) / (2 * Math.PI)).toFixed(2) + '<small>圈</small>';
  }
}

// ---- 运转循环 ----
function loop() {
  if (running()) phi += 0.016 * state.speed;
  if (genAnim.playing) {
    genAnim.t += 0.016 / 2.0;                          // 约 2 秒滚一圈
    if (genAnim.t >= 1) {
      genAnim.t = 1;
      genAnim.playing = false;
      el('genBtn').textContent = '▶ 摆线生成动画';
    }
  }
  // 聚焦视图平滑过渡（拖 K₁ / drp 放大曲线，松手恢复）
  if (focus.t !== focus.target) {
    focus.t += (focus.target - focus.t) * 0.18;
    if (Math.abs(focus.target - focus.t) < 0.001) focus.t = focus.target;
    applyFocus();
  }
  // ②↔③ 三节点镜像过渡（同内摆）：前进 不透明度→位移→缩放；后退反序
  const intoStage3 = stageIndex >= 2;
  if (intoStage3) {
    if (morphT < 0.999) {
      morphT += (1 - morphT) * 0.09;
      if (morphT > 0.999) morphT = 1;
    } else if (Math.abs(eccCur - SIGN * E()) > 0.0005) {
      const tgt = SIGN * E();                    // 外摆啮合位在 −x（SIGN·e）
      eccCur += (tgt - eccCur) * 0.08;
      if (Math.abs(tgt - eccCur) < 0.0005) eccCur = tgt;
    } else if (Math.abs(drpCur - state.drp) > 0.0005) {
      drpCur += (state.drp - drpCur) * 0.08;
      if (Math.abs(state.drp - drpCur) < 0.0005) drpCur = state.drp;
    }
  } else {
    if (drpCur > 0.0005) {
      drpCur += (0 - drpCur) * 0.08;
      if (drpCur < 0.0005) drpCur = 0;
    } else if (Math.abs(eccCur) > 0.0005) {
      eccCur += (0 - eccCur) * 0.08;
      if (Math.abs(eccCur) < 0.0005) eccCur = 0;
    } else if (morphT > 0.001) {
      morphT += (0 - morphT) * 0.09;
      if (morphT < 0.001) morphT = 0;
    }
  }
  // ④ 机构静态啮合位（memberPose 用）+ 视点下移过渡
  const meshTarget = stageIndex >= 2 ? 1 : 0;
  if (meshT !== meshTarget) {
    meshT += (meshTarget - meshT) * 0.08;
    if (Math.abs(meshTarget - meshT) < 0.001) meshT = meshTarget;
  }
  const wTarget = stageIndex === 3 ? -state.din / 2 : 0;
  if (wOff !== wTarget) {
    wOff += (wTarget - wOff) * 0.1;
    if (Math.abs(wTarget - wOff) < 0.001) wOff = wTarget;
  }
  draw();
  requestAnimationFrame(loop);
}

function setPlaying(v) {
  playing = v;
  el('play').textContent = playing ? '⏸ 暂停' : '▶ 运转';
  el('play').classList.toggle('playing', playing);
}

// ---- 参数联动 ----
function applyParams() {
  const e = E(), k2 = K2();
  el('zcV').textContent = state.zc;
  el('zpV').textContent = state.zc + 1;
  el('ratioBadge').textContent = '1 : ' + (state.zc + 1);
  el('RpV').innerHTML = state.Rp + '<small>mm</small>';
  el('dpV').innerHTML = state.dp.toFixed(1) + '<small>mm</small>';
  el('k1V').textContent = state.k1.toFixed(2);
  el('eV').innerHTML = e.toFixed(2) + '<small>mm</small>';
  el('drpV').innerHTML = state.drp.toFixed(2) + '<small>mm</small>';
  el('dinV').innerHTML = state.din.toFixed(1) + '<small>mm</small>';
  el('capRV').innerHTML = state.capR.toFixed(1) + '<small>mm</small>';
  el('k2V').textContent = k2.toFixed(2);
  const k2Note = el('k2Note');
  k2Note.textContent = k2 > 1 ? '✓ 针不重叠' : '⚠ 针齿干涉';
  k2Note.className = k2 > 1 ? 'ok' : (k2 > 0.85 ? 'warn' : 'danger');
  // 凸瓣数 zp+1 三的倍数 → 三片 120° 才均布啮合
  const lobes = state.zc + 2;
  el('lobesV').textContent = lobes;
  const ln = el('lobeNote');
  ln.textContent = lobes % 3 === 0 ? '✓ 三片均布' : '⚠ 非3倍，三片干涉';
  ln.className = lobes % 3 === 0 ? 'ok' : 'danger';
  draw();
}

// ---- 阶段切换（点击上方圆点；面板程序滚动对齐，无手势）----
const stagesEl = el('stages');
function setStage(i) {
  stageIndex = i;
  document.querySelectorAll('.stage-dot').forEach((d, k) => d.classList.toggle('active', k === i));
  el('stepHint').innerHTML = STAGE_SUB[i];
  // 离开 ② 时停掉生成动画
  if (i !== 1 && genAnim.playing) {
    genAnim.playing = false; genAnim.t = 0;
    el('genBtn').textContent = '▶ 摆线生成动画';
  }
  // 切到非 ④ 时停止运转并复位
  if (i !== 3) {
    setPlaying(false);
    phi = 0;
  }
  stagesEl.scrollTo({ left: i * stagesEl.clientWidth, behavior: 'smooth' });
  resize();   // 按阶段内容重 fit（①②③ → Rp；④ → 胶囊机构）
  draw();
}
document.querySelectorAll('.stage-dot').forEach(d => {
  d.addEventListener('click', () => setStage(+d.dataset.i));
});

// ---- 手势缩放（双指捏合 / 滚轮）----
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
el('genBtn').addEventListener('click', () => {
  genAnim.t = 0;
  genAnim.playing = true;
  el('genBtn').textContent = '⏳ 生成中…';
});
el('stackSw').addEventListener('click', () => {
  state.stack = !state.stack;
  el('stackSw').classList.toggle('on', state.stack);
  draw();
});
['zc', 'dp', 'Rp', 'k1', 'drp', 'din', 'capR'].forEach(id => {
  el(id).addEventListener('input', () => {
    state[id] = +el(id).value;
    applyParams();
  });
});
// 拖 K₁ / drp 时放大聚焦曲线处，松手恢复
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
cv.addEventListener('touchstart', e => e.preventDefault(), { passive: false });
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
