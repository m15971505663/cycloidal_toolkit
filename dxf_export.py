# -*- coding: utf-8 -*-
"""DXF 导出：内摆线 / 外摆线 各零部件的加工轮廓。

依赖：ezdxf（pip install ezdxf）
使用 ezdxf 生成 .dxf，几何全部换算成 mm，与 cycloid_anim.py 的绘图参数一致。
轮廓用闭合 LWPOLYLINE；圆用 CIRCLE。
"""

import os
import numpy as np


def _add_closed_spline(msp, pts, dn=None, degree=3):
    """把闭合轮廓写成闭合三次样条（SPLINE），以精准的样条代替多段线弦逼近。

    - 先用 ezdxf 的 fit_points_to_cad_cv 把插值点转成控制点 + 节点向量，
      写出带明确控制点的 SPLINE（73=控制点数），所有 CAD/查看器都能正确显示；
      若只写拟合点(11)很多查看器会显示为空。
    - dn 给定则等距抽稀到 dn 点（光滑圆弧段可抽稀）；齿廓尖端曲率大，None 保留全部点最准。
    """
    if dn is not None and len(pts) > dn:
        idx = np.linspace(0, len(pts) - 1, dn, dtype=int)
        idx = np.unique(idx)
        pts = pts[idx]
    try:
        from ezdxf.math import fit_points_to_cad_cv
        bs = fit_points_to_cad_cv([(float(x), float(y)) for x, y in pts])
    except Exception:
        bs = None
    if bs is not None and len(bs.control_points) >= 4:
        spline = msp.add_spline(degree=degree)
        spline.control_points = [tuple(float(v) for v in c) for c in bs.control_points]
        spline.knots = list(bs.knots())
        spline.closed = True
        return spline
    # 兜底：控制点不足时退回多段线，保证齿廓仍可显示
    msp.add_lwpolyline([(float(x), float(y), 0.0) for x, y in pts], close=True)
    return None


def _add_circle(msp, cx, cy, r):
    msp.add_circle((float(cx), float(cy), 0.0), float(r))


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

    # 2) 摆线盘：齿廓（闭合多段线） + nw 个 W 孔（圆）
    doc = new_doc(); msp = doc.modelspace()
    tooth = tooth_pts()                       # 盘以自身形心为原点
    _add_closed_spline(msp, tooth)
    for i in range(nw):
        a = i / nw * 2 * np.pi
        _add_circle(msp, params['Rw'] * np.cos(a), params['Rw'] * np.sin(a), holeR)
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
        cap = capsule_outline(axc, ay, bx, by, capR)
        return cap, np.stack([tx, ty], axis=1), (bx, by)

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
        _add_closed_spline(msp, cap, dn=64)           # 胶囊外沿（样条，光滑圆弧可抽稀）
        _add_closed_spline(msp, tooth)                # 齿廓（样条）
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
