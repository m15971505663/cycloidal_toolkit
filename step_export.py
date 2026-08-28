# -*- coding: utf-8 -*-
"""STEP 三维模型导出：内摆线 / 外摆线 各零部件。

依赖：cadquery（pip install cadquery）
几何轮廓复用 gear_geom.py，与 DXF 导出完全一致（2D 轮廓 → 挤出 → 布尔）。
轴向尺寸参数来自 params（界面可调）：
  内摆：L_disc 盘厚 / L_pin 针齿长 / L_wpin W销长 / L_sleeve 偏心套轴长 / r_shaft 输入轴半径
  外摆：L_member 外摆盘厚 / L_pin 针齿长 / L_shaft 输入轴长 / r_shaft 输入轴半径
"""

import os
import numpy as np

from gear_geom import resample_arclen, trochoid_tooth, capsule_outline


def save(iostrm, filename):
    from cadquery import exporters
    if not filename.lower().endswith('.step'):
        filename += '.step'
    os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
    exporters.export(iostrm, filename)
    return filename


def _extrude_solid(pts, h):
    import cadquery as cq
    w = (cq.Workplane("XY").polyline([(float(x), float(y)) for x, y in pts])
         .close().extrude(float(h)))
    return w.val()


def _cylinder(r, h, cx, cy, cz=0.0):
    import cadquery as cq
    w = cq.Workplane("XY").circle(float(r)).extrude(float(h))
    return w.val().translate(cq.Vector(float(cx), float(cy), float(cz)))


def _union(shapes):
    from cadquery import Compound
    if len(shapes) == 1:
        return shapes[0]
    return Compound.makeCompound(shapes)


# =================== 内摆线 ===================
def export_inner(params, out_dir, dbl=True):
    """内摆线：导出 4 份 STEP
      1) fixed_pins.step        zp 根针齿圆柱（φdp, 长 L_pin）
      2) cycloid_disc.step      摆线盘：齿廓挤出 L_disc − nw 个 W 孔 − 1 个偏心孔(eccR, 偏 e)
      3) w_pins.step            nw 根 W 销圆柱（φdw, 长 L_wpin）
      4) eccentric_sleeve.step  带中心轴的偏心轴颈：轴(r_shaft,L_sleeve) + 偏心颈(eccR,偏 e)
                                （双盘 → 两段轴颈 180° 相差）
    """
    zc = params['zc']
    zp = zc + 1
    e = params['k1'] * params['Rp'] / zp
    rp = params['dp'] / 2
    wR = params['dw'] / 2
    holeR = wR + e
    nw = params['nw']
    eccR = params['eccR']
    L_pin = params['L_pin']
    L_disc = params['L_disc']
    L_wpin = params['L_wpin']
    L_sleeve = params['L_sleeve']
    r_shaft = params['r_shaft']

    files = {}

    # 1) 固定针齿：zp 根圆柱
    pins = []
    for i in range(zp):
        a = i / zp * 2 * np.pi
        pins.append(_cylinder(rp, L_pin, params['Rp'] * np.cos(a),
                              params['Rp'] * np.sin(a), cz=-L_pin / 2))
    files['fixed_pins'] = save(_union(pins), os.path.join(out_dir, 'fixed_pins.step'))

    # 2) 摆线盘：齿廓挤出 − W孔 − 偏心孔
    disc = _extrude_solid(resample_arclen(trochoid_tooth(params, zp, e, rp, +1), 0.15),
                          L_disc)
    for i in range(nw):
        a = i / nw * 2 * np.pi
        tool = _cylinder(holeR, L_disc + 1, params['Rw'] * np.cos(a),
                         params['Rw'] * np.sin(a), cz=-0.5)
        disc = disc.cut(tool)
    ecc_tool = _cylinder(eccR, L_disc + 1, e, 0.0, cz=-0.5)
    disc = disc.cut(ecc_tool)
    files['cycloid_disc'] = save(disc, os.path.join(out_dir, 'cycloid_disc.step'))

    # 3) W 销：nw 根圆柱
    wps = []
    for i in range(nw):
        a = i / nw * 2 * np.pi
        wps.append(_cylinder(wR, L_wpin, params['Rw'] * np.cos(a),
                             params['Rw'] * np.sin(a), cz=-L_wpin / 2))
    files['w_pins'] = save(_union(wps), os.path.join(out_dir, 'w_pins.step'))

    # 4) 偏心套：轴 + 偏心轴颈（单盘 1 段 / 双盘 2 段 180° 相差，轴颈沿轴向分段）
    parts = [_cylinder(r_shaft, L_sleeve, 0, 0, cz=-L_sleeve / 2)]
    if not dbl:
        bands = [(e, 0.0, L_sleeve)]
        cz0 = -L_sleeve / 2
        for cx, cy, hb in bands:
            parts.append(_cylinder(eccR, hb, cx, cy, cz=cz0))
    else:
        hb = L_sleeve / 2
        parts.append(_cylinder(eccR, hb, e, 0.0, cz=-L_sleeve / 2))
        parts.append(_cylinder(eccR, hb, -e, 0.0, cz=0.0))
    files['eccentric_sleeve'] = save(_union(parts),
                                     os.path.join(out_dir, 'eccentric_sleeve.step'))

    return files


# =================== 外摆线 ===================
def export_outer(params, out_dir, stack=True):
    """外摆线：导出 5 份 STEP
      1) output_pins.step   zp 根针齿圆柱（φdp, 长 L_pin）
      2) input_shaft.step   轴(r_shaft,L_shaft) + 3 段偏心颈(半径 eccR, 偏 e, 相位120°)
      3~5) member_0/1/2.step 胶囊 − 齿廓 − 偏心圆的 2D 区域挤出 L_member
    """
    zc = params['zc']
    zp = zc + 1
    e = params['k1'] * params['Rp'] / zp
    rp = params['dp'] / 2
    eccR = params['eccR']
    din = params['din']
    capR = params['capR']
    s = -1
    L_pin = params['L_pin']
    L_member = params['L_member']
    L_shaft = params['L_shaft']
    r_shaft = params['r_shaft']

    files = {}

    # 1) 输出针齿
    pins = []
    for i in range(zp):
        a = i / zp * 2 * np.pi
        pins.append(_cylinder(rp, L_pin, params['Rp'] * np.cos(a),
                              params['Rp'] * np.sin(a), cz=-L_pin / 2))
    files['output_pins'] = save(_union(pins), os.path.join(out_dir, 'output_pins.step'))

    # 2) 输入轴：轴 + 3 段偏心颈（沿轴向按 L_member 排布）
    nparts = 3 if stack else 1
    shaft_parts = [_cylinder(r_shaft, L_shaft, 0, 0, cz=-L_shaft / 2)]
    for k in range(nparts):
        phase = 2 * np.pi * k / nparts if stack else 0.0
        cx = s * e * np.cos(phase)
        cy = s * e * np.sin(phase)
        cz = -L_member * nparts / 2.0 + k * L_member
        shaft_parts.append(_cylinder(eccR, L_member, cx, cy, cz=cz))
    files['input_shaft'] = save(_union(shaft_parts),
                                os.path.join(out_dir, 'input_shaft.step'))

    # 3~5) 三个外摆盘
    for k in range(nparts):
        phase = 2 * np.pi * k / nparts if stack else 0.0
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

        # 胶囊 − 齿廓 − 偏心圆（与 2D evenodd 镂空一致）
        member = _extrude_solid(cap, L_member)
        import cadquery as cq
        tooth_tool = _extrude_solid(tooth, L_member + 1).translate(cq.Vector(0, 0, -0.5))
        member = member.cut(tooth_tool)
        ecc_tool = _cylinder(eccR, L_member + 1, bx, by, cz=-0.5)
        member = member.cut(ecc_tool)

        key = 'member_%d' % k
        files[key] = save(member, os.path.join(out_dir, '%s.step' % key))

    return files


def export_current(params, out_dir, mode, dbl, stack):
    """按当前模式导出，返回生成的文件名列表。"""
    if mode == 'inner':
        f = export_inner(params, out_dir, dbl=dbl)
    else:
        f = export_outer(params, out_dir, stack=stack)
    return list(f.values())