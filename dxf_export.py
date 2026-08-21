# -*- coding: utf-8 -*-
"""DXF 导出：内摆线 / 外摆线 各零部件的加工轮廓。

依赖：ezdxf（pip install ezdxf）
使用 ezdxf 生成 .dxf，几何全部换算成 mm，与 cycloid_anim.py 的绘图参数一致。
轮廓用闭合 LWPOLYLINE；圆用 CIRCLE。
"""

import os
import numpy as np


def _add_polyline(msp, pts, closed=True):
    """pts: Nx2 (mm)，写成闭合多段线（保留真实圆弧用 LWPOLYLINE 顶点足够密）。"""
    msp.add_lwpolyline([(float(x), float(y), 0.0) for x, y in pts], close=closed)


def _add_circle(msp, cx, cy, r):
    msp.add_circle((float(cx), float(cy), 0.0), float(r))


def resample_arclen(pts, max_step):
    """把闭合轮廓按弧长重新采样，保证相邻点弦距 ≤ max_step。

    等 t 采样在曲率大的部位（凹齿 / 凸齿）弦距大、显得粗糙；
    按弧长均匀采样会在这些部位自动加密点，齿形各处平滑度一致。
    """
    pts = np.asarray(pts, dtype=float)
    # 记点间累积弧长（闭合：末尾再连回起点）
    diff = np.diff(pts, axis=0)
    seg = np.hypot(diff[:, 0], diff[:, 1])
    close = np.hypot(pts[0, 0] - pts[-1, 0], pts[0, 1] - pts[-1, 1])
    seg = np.append(seg, close)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return pts
    n = max(2, int(np.ceil(total / max_step)))
    s_target = np.linspace(0.0, total - 1e-9, n)
    # 插值（闭合，用重复首点的 Python 版线性插值）
    # 把点序列扩展一个周期便于循环插值
    pts_ext = np.concatenate([pts, pts[:1]], axis=0)
    cumc = np.concatenate([[0.0], np.cumsum(
        np.hypot(np.diff(pts_ext[:, 0]), np.diff(pts_ext[:, 1])))])
    out = np.empty((n, 2))
    j = 0
    for i, s in enumerate(s_target):
        while j < len(cumc) - 1 and cumc[j + 1] < s:
            j += 1
        t = (s - cumc[j]) / max(cumc[j + 1] - cumc[j], 1e-12)
        out[i] = pts_ext[j] + t * (pts_ext[j + 1] - pts_ext[j])
    return out


# ---- 通用：画闭合多段线的轮廓（可直接存 .dxf，不想在模块里引 ezdxf 依赖时的常量名）----
# 这里直接引入 ezdxf，函数均返回 doc

def new_doc():
    import ezdxf
    doc = ezdxf.new('R2010')
    doc.units = 4   # 毫米
    return doc


def save_doc(doc, filename):
    if not filename.lower().endswith('.dxf'):
        filename += '.dxf'
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    doc.saveas(filename)
    return filename


# =================== 内摆线 ===================
def export_inner(params, out_dir, SIGN=+1, dbl=True):
    """内摆线：导出 4 份 DXF
      1) 固定针齿        fixed_pins.dxf
      2) 摆线盘（含W孔）  cycloid_disc.dxf
      3) W 销            w_pins.dxf
      4) 偏心套          eccentric_sleeve.dxf（双摆线盘 → 两个偏心圆，180° 相差）
    """
    zc = params['zc']
    zp = zc + 1
    e = params['k1'] * params['Rp'] / zp
    rp = params['dp'] / 2
    wR = params['dw'] / 2
    holeR = wR + e
    nw = params['nw']
    eccR = params['eccR']

    # --- 齿廓（内摆 SIGN=+1，内缩）---
    def tooth_pts(SIGN=1):
        R, n = params['Rp'], zp
        off = rp + params['drp']
        t = np.linspace(0, 2 * np.pi, zp * 64)
        ct, st = np.cos(t), np.sin(t)
        cnt, snt = np.cos(n * t), np.sin(n * t)
        s = SIGN
        xa = R * ct - s * e * cnt
        ya = R * st - e * snt
        dxa = -R * st + s * n * e * snt
        dya = R * ct - n * e * cnt
        denom = np.hypot(dxa, dya); denom[denom == 0] = 1
        o = s * off / denom
        return np.stack([xa + o * (-dya), ya + o * dxa], axis=1)

    files = {}

    # 1) 固定针齿：zp 个圆，半径 rp，中心在 Rp 圆上
    doc = new_doc(); msp = doc.modelspace()
    for i in range(zp):
        a = i / zp * 2 * np.pi
        _add_circle(msp, params['Rp'] * np.cos(a), params['Rp'] * np.sin(a), rp)
    files['fixed_pins'] = save_doc(doc, os.path.join(out_dir, 'fixed_pins.dxf'))

    # 2) 摆线盘：齿廓（闭合多段线，按弧长加密确保凹齿不粗糙） + nw 个 W 孔（圆）
    #    + 1 个偏心套圆（中心相对盘心偏移 e；双盘是同一零件装 180°，DXF 仍只有 1 个偏心圆）
    doc = new_doc(); msp = doc.modelspace()
    tooth = tooth_pts()                       # 盘以自身形心为原点
    _add_polyline(msp, resample_arclen(tooth, 0.15), closed=True)
    for i in range(nw):
        a = i / nw * 2 * np.pi
        _add_circle(msp, params['Rw'] * np.cos(a), params['Rw'] * np.sin(a), holeR)
    _add_circle(msp, e, 0.0, eccR)
    files['cycloid_disc'] = save_doc(doc, os.path.join(out_dir, 'cycloid_disc.dxf'))

    # 3) W 销：nw 个圆，半径 wR，中心在 Rw 圆上（输出销，参考位）
    doc = new_doc(); msp = doc.modelspace()
    for i in range(nw):
        a = i / nw * 2 * np.pi
        _add_circle(msp, params['Rw'] * np.cos(a), params['Rw'] * np.sin(a), wR)
    files['w_pins'] = save_doc(doc, os.path.join(out_dir, 'w_pins.dxf'))

    # 4) 偏心套：偏心圆，中心相对输入轴偏移 e（双盘 → 两个偏心圆 180° 相差）
    doc = new_doc(); msp = doc.modelspace()
    centers = [(e, 0.0)] if not dbl else [(e, 0.0), (-e, 0.0)]
    for cx, cy in centers:
        _add_circle(msp, cx, cy, eccR)
    files['eccentric_sleeve'] = save_doc(doc, os.path.join(out_dir, 'eccentric_sleeve.dxf'))

    return files


# =================== 外摆线 ===================
def export_outer(params, out_dir, SIGN=-1, stack=True):
    """外摆线：导出 5 份 DXF
      1) 输出针齿      output_pins.dxf
      2) 输入轴（三个偏心套圆组成的输入轴） input_shaft.dxf
      3~5) 三个外摆盘（三片 120° 相位） member_0.dxf / member_1.dxf / member_2.dxf
    """
    zc = params['zc']
    zp = zc + 1
    e = params['k1'] * params['Rp'] / zp
    rp = params['dp'] / 2
    eccR = params['eccR']
    din = params['din']
    capR = params['capR']
    s = SIGN

    def tooth_pts():
        R, n = params['Rp'], zp
        off = rp + params['drp']
        t = np.linspace(0, 2 * np.pi, zp * 64)
        ct, st = np.cos(t), np.sin(t)
        cnt, snt = np.cos(n * t), np.sin(n * t)
        xa = R * ct - s * e * cnt
        ya = R * st - e * snt
        dxa = -R * st + s * n * e * snt
        dya = R * ct - n * e * cnt
        denom = np.hypot(dxa, dya); denom[denom == 0] = 1
        o = s * off / denom
        return np.stack([xa + o * (-dya), ya + o * dxa], axis=1)

    def capsule_outline(axc, ay, bx, by, r):
        a_arc = [(axc + r * np.cos(a), ay + r * np.sin(a)) for a in np.linspace(0, np.pi, 48)]
        b_arc = [(bx + r * np.cos(a), by + r * np.sin(a)) for a in np.linspace(np.pi, 2 * np.pi, 48)]
        return np.array(a_arc + [(bx - r, by)] + b_arc + [(axc + r, ay)])

    def member_pts(phase):
        # A=摆线轮中心（刚体平动中心=偏心），B=偏心套中心（输入轴处），rot=相位齿廓错位
        axc = s * e * np.cos(phase)
        ay = s * e * np.sin(phase)
        bx = s * e * np.cos(phase)
        by = s * e * np.sin(phase) - din
        rot = phase / (zp + 1)
        cr, sr = np.cos(rot), np.sin(rot)
        tooth = tooth_pts()
        tx = tooth[:, 0] * cr - tooth[:, 1] * sr + axc
        ty = tooth[:, 0] * sr + tooth[:, 1] * cr + ay
        tooth = np.stack([tx, ty], axis=1)
        tooth = resample_arclen(tooth, 0.15)      # 按弧长加密，凸齿不粗糙
        cap = capsule_outline(axc, ay, bx, by, capR)
        cap = resample_arclen(cap, 0.2)           # 胶囊外沿圆弧也按弧长加密
        return cap, tooth, (bx, by)

    files = {}

    # 1) 输出针齿：zp 个圆，半径 rp（针齿固定在针齿圆上，静止参考）
    doc = new_doc(); msp = doc.modelspace()
    for i in range(zp):
        a = i / zp * 2 * np.pi
        _add_circle(msp, params['Rp'] * np.cos(a), params['Rp'] * np.sin(a), rp)
    files['output_pins'] = save_doc(doc, os.path.join(out_dir, 'output_pins.dxf'))

    # 2) 输入轴：由三个偏心套圆组成（三片偏心相位 120°，圆心各自偏移 e，绕输入轴 (0,-din)）
    doc = new_doc(); msp = doc.modelspace()
    for k in range(3 if stack else 1):
        phase = 2 * np.pi * k / 3 if stack else 0.0
        bx = s * e * np.cos(phase)
        by = s * e * np.sin(phase) - din if stack else -din + 0.0
        _add_circle(msp, bx, by, eccR)
    files['input_shaft'] = save_doc(doc, os.path.join(out_dir, 'input_shaft.dxf'))

    # 3~5) 三个外摆盘（每片一份 DXF；含胶囊外沿 + 齿廓 + 本片输入轴的偏心套圆 eccR）
    for k in range(3 if stack else 1):
        phase = 2 * np.pi * k / 3 if stack else 0.0
        cap, tooth, (bx, by) = member_pts(phase)
        doc = new_doc(); msp = doc.modelspace()
        _add_polyline(msp, cap, closed=True)          # 胶囊外沿
        _add_polyline(msp, tooth, closed=True)        # 齿廓
        _add_circle(msp, bx, by, eccR)                # 输入轴偏心套圆
        key = 'member_%d' % k
        files[key] = save_doc(doc, os.path.join(out_dir, '%s.dxf' % key))

    return files


def export_current(params, out_dir, mode, dbl, stack):
    """按当前模式导出，返回生成的文件名列表。"""
    if mode == 'inner':
        f = export_inner(params, out_dir, SIGN=+1, dbl=dbl)
    else:
        f = export_outer(params, out_dir, SIGN=-1, stack=stack)
    return list(f.values())
