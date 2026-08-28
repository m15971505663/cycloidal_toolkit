# -*- coding: utf-8 -*-
"""DXF 导出：内摆线 / 外摆线 各零部件的加工轮廓。

依赖：ezdxf（pip install ezdxf）
几何轮廓（齿廓 / 胶囊 / 弧长重采样）复用 gear_geom.py，与 STEP 导出完全一致。
圆用 CIRCLE；轮廓用闭合 LWPOLYLINE。
"""

import os
import numpy as np

from gear_geom import resample_arclen, trochoid_tooth, capsule_outline


def _add_polyline(msp, pts, closed=True):
    msp.add_lwpolyline([(float(x), float(y), 0.0) for x, y in pts], close=closed)


def _add_circle(msp, cx, cy, r):
    msp.add_circle((float(cx), float(cy), 0.0), float(r))


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
      2) 摆线盘（含W孔+偏心圆） cycloid_disc.dxf
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
    tooth = resample_arclen(trochoid_tooth(params, zp, e, rp, +1), 0.15)

    files = {}

    # 1) 固定针齿：zp 个圆，半径 rp，中心在 Rp 圆上
    doc = new_doc(); msp = doc.modelspace()
    for i in range(zp):
        a = i / zp * 2 * np.pi
        _add_circle(msp, params['Rp'] * np.cos(a), params['Rp'] * np.sin(a), rp)
    files['fixed_pins'] = save_doc(doc, os.path.join(out_dir, 'fixed_pins.dxf'))

    # 2) 摆线盘：齿廓 + nw 个 W 孔 + 1 个偏心套圆（双盘是同一零件装180°，仍只有1个偏心圆）
    doc = new_doc(); msp = doc.modelspace()
    _add_polyline(msp, tooth, closed=True)
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

    def member_pts(phase):
        # A=摆线轮中心（刚体平动中心=偏心），B=偏心套中心（输入轴处），rot=相位齿廓错位
        axc = s * e * np.cos(phase)
        ay = s * e * np.sin(phase)
        bx = s * e * np.cos(phase)
        by = s * e * np.sin(phase) - din
        rot = phase / (zp + 1)
        cr, sr = np.cos(rot), np.sin(rot)
        tooth = trochoid_tooth(params, zp, e, rp, s)
        tx = tooth[:, 0] * cr - tooth[:, 1] * sr + axc
        ty = tooth[:, 0] * sr + tooth[:, 1] * cr + ay
        tooth = resample_arclen(np.stack([tx, ty], axis=1), 0.15)
        cap = resample_arclen(capsule_outline(axc, ay, bx, by, capR), 0.2)
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
        by = s * e * np.sin(phase) - din
        _add_circle(msp, bx, by, eccR)
    files['input_shaft'] = save_doc(doc, os.path.join(out_dir, 'input_shaft.dxf'))

    # 3~5) 三个外摆盘（每片一份 DXF；含胶囊外沿 + 齿廓 + 本片输入轴的偏心套圆 eccR）
    for k in range(3 if stack else 1):
        phase = 2 * np.pi * k / 3 if stack else 0.0
        cap, tooth, (bx, by) = member_pts(phase)
        doc = new_doc(); msp = doc.modelspace()
        _add_polyline(msp, cap, closed=True)
        _add_polyline(msp, tooth, closed=True)
        _add_circle(msp, bx, by, eccR)
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