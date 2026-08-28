# -*- coding: utf-8 -*-
"""共享几何计算：内摆 / 外摆 的齿廓、胶囊外沿、弧长重采样。

DXF 导出与 STEP 导出共用这一组纯 numpy 函数，保证两种产出的轮廓完全一致。
"""

import numpy as np


def resample_arclen(pts, max_step):
    """把闭合轮廓按弧长重新采样，保证相邻点弦距 ≤ max_step。

    等 t 采样在曲率大的部位（凹齿 / 凸齿）弦距大、显得粗糙；
    按弧长均匀采样会在这些部位自动加密点，齿形各处平滑度一致。
    """
    pts = np.asarray(pts, dtype=float)
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
    pts_ext = np.concatenate([pts, pts[:1]], axis=0)
    cumc = np.concatenate([[0.0], np.cumsum(
        np.hypot(np.diff(pts_ext[:, 0]), np.diff(pts_ext[:, 1])))])
    out = np.empty((n, 2))
    j = 0
    for i, s in enumerate(s_target):
        while j < len(cumc) - 1 and cumc[j + 1] < s:
            j += 1
        tfrac = (s - cumc[j]) / max(cumc[j + 1] - cumc[j], 1e-12)
        out[i] = pts_ext[j] + tfrac * (pts_ext[j + 1] - pts_ext[j])
    return out


def trochoid_tooth(params, zp, e, rp, sign, drp=None, n_per_lobe=64):
    """摆线齿廓点集 Nx2（法向偏移 rp+drp 后的齿廓，非针心轨迹）。

    sign=+1 内摆（齿廓内缩）；sign=-1 外摆（齿廓外胀包裹针齿）。
    params 提供 Rp（销布置圆半径），drp 缺省取 params['drp']。
    """
    R = params['Rp']
    off = rp + (params['drp'] if drp is None else drp)
    n = zp
    t = np.linspace(0, 2 * np.pi, zp * n_per_lobe)
    ct, st = np.cos(t), np.sin(t)
    cnt, snt = np.cos(n * t), np.sin(n * t)
    xa = R * ct - sign * e * cnt
    ya = R * st - e * snt
    dxa = -R * st + sign * n * e * snt
    dya = R * ct - n * e * cnt
    denom = np.hypot(dxa, dya)
    denom[denom == 0] = 1
    o = sign * off / denom
    return np.stack([xa + o * (-dya), ya + o * dxa], axis=1)


def capsule_outline(axc, ay, bx, by, r):
    """外摆胶囊外沿轮廓点集（A=摆线轮中心，B=偏心套中心，r=面板半径）。"""
    a_arc = [(axc + r * np.cos(a), ay + r * np.sin(a)) for a in np.linspace(0, np.pi, 48)]
    b_arc = [(bx + r * np.cos(a), by + r * np.sin(a)) for a in np.linspace(np.pi, 2 * np.pi, 48)]
    return np.array(a_arc + [(bx - r, by)] + b_arc + [(axc + r, ay)])


def poly_centroid(pts):
    """多边形形心（闭合，按面积加权），用于 STEP 部件以自身形心摆放。"""
    pts = np.asarray(pts, dtype=float)
    x = pts[:, 0]
    y = pts[:, 1]
    # 鞋带公式
    s0 = np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]) + x[-1] * y[0] - x[0] * y[-1]
    area = 0.5 * s0
    if abs(area) < 1e-12:
        return pts.mean(axis=0)
    cx = (np.dot(x[:-1] + x[1:], x[:-1] * y[1:] - x[1:] * y[:-1]) +
          (x[-1] + x[0]) * (x[-1] * y[0] - x[0] * y[-1])) / (6.0 * area)
    cy = (np.dot(y[:-1] + y[1:], x[:-1] * y[1:] - x[1:] * y[:-1]) +
          (y[-1] + y[0]) * (x[-1] * y[0] - x[0] * y[-1])) / (6.0 * area)
    return np.array([cx, cy])