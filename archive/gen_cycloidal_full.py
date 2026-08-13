# -*- coding: utf-8 -*-
"""参数化摆线针轮减速器 · 整机（6 类零件，多 body 装配布局）。

摆线齿廓数学移植自 WebPreviewer/cycloidal_reducer.html 的 makeCycloidGeo()。
通过 /exec 注入 Fusion 主线程：
  curl -G http://127.0.0.1:9099/exec --data-urlencode "code@scripts/gen_cycloidal_full.py"

说明：
  - 当前是零件设计文档（不能 addNewComponent），所以每个零件 = 一个独立 body，
    在浏览器树里可单独显示/隐藏，方便拆开看结构。
  - 所有产物名字带 "CR_" 前缀；脚本开头会先 purge 掉上次的 CR_* 和单盘脚本的旧产物。
  - Z 轴 = 减速器主轴线，装配布局和 cycloidal_reducer.html 完全一致。
  - Fusion API 的 Point3D / ValueInput.createByReal 内部用 cm，mm 参数喂 API 时统一 /10。
"""
import math, traceback
import adsk.core, adsk.fusion  # /exec 上下文通常已有 adsk，显式 import 更稳

PREFIX = "CR"          # 本脚本所有产物的名字前缀（purge 用）
PTS_PER_TOOTH = 48     # 摆线齿廓每齿采样点数

PARAMS = dict(
    # 摆线齿廓
    zp=11, e=2.6, rp=4.2, drp=0.6, Rp=38.0,
    # 盘片
    b=14.0, discGap=22.0,          # 盘厚 / 两片盘中心距
    pinN=8, pinR=20.0, pinSize=2.5,  # W 机构：销数 / 分布圆 / 销半径
    eccR=11.0, centerGap=1.8,        # 偏心套半径 / 中心孔额外间隙
    # 输入/输出轴
    inR=7.0, inLen=90.0,
    outR=9.0, outLen=60.0,
    housingLen=62.0,
)


def main():
    P = PARAMS
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    if not des:
        return {"error": "无活动 Design（先打开/新建一个 Fusion 设计）"}
    root = des.rootComponent
    extrudes = root.features.extrudeFeatures
    NewBody = adsk.fusion.FeatureOperations.NewBodyFeatureOperation

    def cm(v):
        return v / 10.0   # mm → cm（Fusion 内部单位）

    # ---------- purge 上次产物（顺序：拉伸 → 草图 → 基准面，按依赖关系）----------
    purged = []
    for f in list(root.features.extrudeFeatures):
        if f.name.startswith(PREFIX) or f.name.startswith("摆线轮拉伸"):
            purged.append("ext:" + f.name); f.deleteMe()
    for s in list(root.sketches):
        if s.name.startswith(PREFIX) or s.name.startswith("摆线轮齿廓"):
            purged.append("sk:" + s.name); s.deleteMe()
    for p in list(root.constructionPlanes):
        if p.name.startswith(PREFIX):
            purged.append("pl:" + p.name); p.deleteMe()

    # ---------- helpers ----------
    def offset_plane(z_mm):
        """在 z=z_mm 处建一个平行 XY 的偏移基准面。"""
        planes = root.constructionPlanes
        inp = planes.createInput()
        inp.setByOffset(root.xYConstructionPlane,
                        adsk.core.ValueInput.createByReal(cm(z_mm)))
        pl = planes.add(inp)
        pl.name = "{}_plane_{}".format(PREFIX, round(z_mm, 1))
        return pl

    def pick_profile(sketch):
        """草图里取 loop 数最多的 profile（= 主轮廓，带孔的盘身 / 环形）。"""
        prof, best = None, -1
        for i in range(sketch.profiles.count):
            p = sketch.profiles.item(i)
            nl = p.profileLoops.count
            if nl > best:
                best, prof = nl, p
        return prof, best

    def extrude_one(sketch, z_lo, z_hi, name):
        """单 profile 拉伸成一个 body，命名 body+特征。"""
        prof, nl = pick_profile(sketch)
        ei = extrudes.createInput(prof, NewBody)
        ei.setDistanceExtent(False, adsk.core.ValueInput.createByString("{} mm".format(z_hi - z_lo)))
        ext = extrudes.add(ei)
        ext.name = "{}_{}".format(PREFIX, name)
        ext.bodies.item(0).name = "{}_{}".format(PREFIX, name)
        return nl

    def extrude_each(sketch, z_lo, z_hi, name):
        """草图中多个独立 profile 各自拉伸成一个 body（针齿/W销用）。"""
        n = sketch.profiles.count
        for i in range(n):
            prof = sketch.profiles.item(i)
            ei = extrudes.createInput(prof, NewBody)
            ei.setDistanceExtent(False, adsk.core.ValueInput.createByString("{} mm".format(z_hi - z_lo)))
            ext = extrudes.add(ei)
            ext.name = "{}_{}{}".format(PREFIX, name, i + 1)
            ext.bodies.item(0).name = "{}_{}{}".format(PREFIX, name, i + 1)
        return n

    def cyl_sketch(plane, circles, name):
        """画若干圆（mm）。circles=[(cx,cy,r),...]。"""
        sk = root.sketches.add(plane)
        sk.name = "{}_sk_{}".format(PREFIX, name)
        for (cx, cy, r) in circles:
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cm(cx), cm(cy), 0.0), cm(r))
        return sk

    def build_disc(z_center, ox, oy, profile_phase, name):
        """建一片摆线轮（齿廓 + 中心孔 + W销孔）。
        ox,oy = 盘中心在世界 XY 的偏心位置（盘坐在偏心套上：盘1(+e,0)，盘2(-e,0)）。
          齿廓曲线已把偏心运动 e 算进形状，所以盘必须偏到 ±e 齿才刚好贴针齿
          （验证：偏过去后齿面↔针齿间隙 = drp）。
        profile_phase = 齿廓整体旋转角，对到啮合相位（盘1=0 即 φ=0；盘2=-π/zc 即 φ=π）。
        W 销孔【不】随齿廓旋转，始终对齐世界 W 销（孔半径=销半径+e，容纳偏心滑动）。
        """
        zp, e, rp, drp = P["zp"], P["e"], P["rp"], P["drp"]
        Rp, b = P["Rp"], P["b"]
        pinN, pinR, pinSize = P["pinN"], P["pinR"], P["pinSize"]
        eccR, centerGap = P["eccR"], P["centerGap"]
        N = zp * PTS_PER_TOOTH
        sk = root.sketches.add(offset_plane(z_center - b / 2))
        sk.name = "{}_sk_{}".format(PREFIX, name)
        cp, sp = math.cos(profile_phase), math.sin(profile_phase)
        oc = adsk.core.ObjectCollection.create()
        for k in range(N):
            t = (k / N) * 2.0 * math.pi
            x = Rp * math.cos(t) - e * math.cos(zp * t)
            y = Rp * math.sin(t) - e * math.sin(zp * t)
            dx = -Rp * math.sin(t) + e * zp * math.sin(zp * t)
            dy = Rp * math.cos(t) - e * zp * math.cos(zp * t)
            nx, ny = -dy, dx
            L = math.hypot(nx, ny) or 1.0
            nx /= L; ny /= L
            if nx * x + ny * y < 0:
                nx, ny = -nx, -ny
            px = x - (rp + drp) * nx
            py = y - (rp + drp) * ny
            # 齿廓旋转 profile_phase（啮合相位），再平移到偏心位置 (ox,oy)
            rx = (px * cp - py * sp) + ox
            ry = (px * sp + py * cp) + oy
            oc.add(adsk.core.Point3D.create(cm(rx), cm(ry), 0.0))
        spline = sk.sketchCurves.sketchFittedSplines.add(oc)
        spline.isClosed = True
        # 中心孔（在盘中心 ox,oy，套偏心套）
        sk.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(cm(ox), cm(oy), 0.0), cm(eccR + centerGap))
        # W 销孔：对齐世界 W 销（盘中心 + pinR 圆，不随齿廓旋转）
        holeR = pinSize + e
        for i in range(pinN):
            a = (i / pinN) * 2.0 * math.pi
            sk.sketchCurves.sketchCircles.addByCenterRadius(
                adsk.core.Point3D.create(cm(ox + pinR * math.cos(a)),
                                         cm(oy + pinR * math.sin(a)), 0.0), cm(holeR))
        return extrude_one(sk, z_center - b / 2, z_center + b / 2, name)

    # ---------- 装配（沿 Z 轴）----------
    dg = P["discGap"] / 2.0          # ±11
    eccLen = P["b"] + 8.0            # 偏心套长度
    zc_teeth = P["zp"] - 1
    Rh_in = P["Rp"] + P["rp"] + 0.5      # 针齿壳内径（贴针齿外缘）
    Rh_out = P["Rp"] + P["rp"] + 6.0     # 针齿壳外径
    parts = []

    # 1) 输入轴  z∈[-inLen, 0]，轴心 (0,0)
    z0, z1 = -P["inLen"], 0.0
    extrude_one(cyl_sketch(offset_plane(z0), [(0, 0, P["inR"])], "输入轴"), z0, z1, "输入轴")
    parts.append(("输入轴", [z0, z1], "轴心(0,0) r=%.1f" % P["inR"]))

    # 2) 偏心套 A  z∈[-dg-eccLen/2, -dg+eccLen/2]，外圆心(+e,0) r=eccR，过孔(0,0) r=inR（让输入轴穿过）
    z0, z1 = -dg - eccLen / 2, -dg + eccLen / 2
    extrude_one(cyl_sketch(offset_plane(z0), [(P["e"], 0, P["eccR"]), (0, 0, P["inR"])], "偏心套A"), z0, z1, "偏心套A")
    parts.append(("偏心套A", [z0, z1], "外圆心(+e,0)，驱动盘1"))

    # 3) 摆线轮 1  盘中心(+e,0)坐在偏心套A上，齿廓phase=0（φ=0 啮合位）
    nl1 = build_disc(-dg, +P["e"], 0.0, 0.0, "摆线轮1")
    parts.append(("摆线轮1", [-dg - P["b"] / 2, -dg + P["b"] / 2], "中心(+e,0) phase=0 loops=%d" % nl1))

    # 4) 摆线轮 2  盘中心(-e,0)坐在偏心套B上，齿廓phase=-π/zc（φ=π 啮合位，双片错半齿）
    nl2 = build_disc(+dg, -P["e"], 0.0, -math.pi / zc_teeth, "摆线轮2")
    parts.append(("摆线轮2", [+dg - P["b"] / 2, +dg + P["b"] / 2], "中心(-e,0) phase=-π/%d loops=%d" % (zc_teeth, nl2)))

    # 5) 偏心套 B  z∈[+dg-eccLen/2, +dg+eccLen/2]，外圆心(-e,0)
    z0, z1 = dg - eccLen / 2, dg + eccLen / 2
    extrude_one(cyl_sketch(offset_plane(z0), [(-P["e"], 0, P["eccR"]), (0, 0, P["inR"])], "偏心套B"), z0, z1, "偏心套B")
    parts.append(("偏心套B", [z0, z1], "外圆心(-e,0)，驱动盘2"))

    # 6) 针齿 ×zp  z∈[-housingLen/2+2, +housingLen/2-2]，分布在 Rp 圆上
    z0, z1 = -P["housingLen"] / 2 + 2, P["housingLen"] / 2 - 2
    pin_circles = [(P["Rp"] * math.cos((i / P["zp"]) * 2 * math.pi),
                    P["Rp"] * math.sin((i / P["zp"]) * 2 * math.pi), P["rp"])
                   for i in range(P["zp"])]
    n_pin = extrude_each(cyl_sketch(offset_plane(z0), pin_circles, "针齿"), z0, z1, "针齿")
    parts.append(("针齿×%d" % n_pin, [z0, z1], "分布圆 Rp=%.0f, r=%.1f" % (P["Rp"], P["rp"])))

    # 7) 针齿壳（外壳管）  z∈[-housingLen/2, +housingLen/2]
    z0, z1 = -P["housingLen"] / 2, P["housingLen"] / 2
    extrude_one(cyl_sketch(offset_plane(z0), [(0, 0, Rh_out), (0, 0, Rh_in)], "针齿壳"), z0, z1, "针齿壳")
    parts.append(("针齿壳", [z0, z1], "管 r=%.1f~%.1f" % (Rh_in, Rh_out)))

    # 8) W 销 ×pinN  z∈[-(dg+b+3), +(dg+b+3)]，穿过两片盘
    z0, z1 = -(dg + P["b"] + 3), (dg + P["b"] + 3)
    wpin_circles = [(P["pinR"] * math.cos((i / P["pinN"]) * 2 * math.pi),
                     P["pinR"] * math.sin((i / P["pinN"]) * 2 * math.pi), P["pinSize"])
                    for i in range(P["pinN"])]
    n_wp = extrude_each(cyl_sketch(offset_plane(z0), wpin_circles, "W销"), z0, z1, "W销")
    parts.append(("W销×%d" % n_wp, [z0, z1], "分布圆 pinR=%.0f, r=%.1f" % (P["pinR"], P["pinSize"])))

    # 9) 输出轴  z∈[20, 20+outLen]，轴心(0,0)
    z0, z1 = 20.0, 20.0 + P["outLen"]
    extrude_one(cyl_sketch(offset_plane(z0), [(0, 0, P["outR"])], "输出轴"), z0, z1, "输出轴")
    parts.append(("输出轴", [z0, z1], "轴心(0,0) r=%.1f" % P["outR"]))

    return {
        "document": app.activeDocument.name,
        "purged_previous": purged,
        "ratio": "1:{}".format(zc_teeth),
        "body_count": sum(1 for f in root.features.extrudeFeatures if f.name.startswith(PREFIX)),
        "parts": [{"name": n, "z_mm": [round(z[0], 1), round(z[1], 1)], "note": c} for (n, z, c) in parts],
    }


try:
    _result = main()
except Exception as e:
    _result = {"error": str(e), "tb": traceback.format_exc()}
