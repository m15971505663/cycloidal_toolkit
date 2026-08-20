#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""摆线针轮减速器 · 原理演示（Python 桌面版）

同时支持两种摆线针轮减速器，可在右侧面板切换：

  · 内摆线减速器（hypotrochoid，src/main.js）：摆线轮 + 针齿 + 偏心套 + W 销孔机构
  · 外摆线减速器（hypotrochoid/SIGN=−1，src-outer/main.js）：
      胶囊刚体平动输入，针齿=输出慢转（减速比 1:zp），三片 120° 相位叠装，无 W 机构

左侧实时绘制动画，右侧参数面板，修改参数立即刷新并列出计算式，按钮控制动画启停。

依赖：numpy + matplotlib + PyQt5
    pip install numpy matplotlib PyQt5

用法：
    python3 cycloid_anim.py
"""

import sys
import os
import json
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QFormLayout, QLabel, QSpinBox,
                             QDoubleSpinBox, QPushButton, QCheckBox,
                             QRadioButton, QButtonGroup, QScrollArea, QFrame,
                             QFileDialog)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.patches import Circle


# 禁止滚轮直接改动数值框（避免页面滚动时误改参数）
class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event):
        event.ignore()

# ---- 设计参数（直径按用户习惯，内部换算半径）----
DEFAULT_INNER = {'zc': 14, 'k1': 0.75, 'Rp': 16, 'dp': 2, 'drp': 0.2,
                 'nw': 6, 'dw': 2, 'Rw': 10, 'eccR': 7, 'speed': 1, 'dbl': True,
                 'din': 40, 'capR': 28, 'stack': True}
DEFAULT_OUTER = {'zc': 10, 'k1': 0.75, 'Rp': 20, 'dp': 3, 'drp': 0.2,
                 'nw': 6, 'dw': 2, 'Rw': 10, 'eccR': 7, 'speed': 1, 'dbl': True,
                 'din': 40, 'capR': 28, 'stack': True}

params_inner = dict(DEFAULT_INNER)
params_outer = dict(DEFAULT_OUTER)

mode = 'inner'      # 'inner' 内摆 / 'outer' 外摆
SIGN = +1           # 外摆核心开关（内摆 +1 / 外摆 −1）

# params 永远指向当前模式对应的参数字典（内摆/外摆各自独立记忆）
params = params_inner

phi = 0.0           # 输入角（内摆：偏心公转；外摆：胶囊平动相位，弧度）
playing = False     # 动画运行标记（由“开始动画”按钮控制）

# ---- 参数持久化（保存到 JSON；重开软件自动恢复上次参数）----
def param_file():
    return os.environ.get('CYCLOID_PARAMS_FILE',
                          os.path.join(os.path.expanduser('~'), '.cycloid_anim_params.json'))

def save_params_to_file(path):
    data = {'mode': mode,
            'inner': dict(params_inner),
            'outer': dict(params_outer)}
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print('保存参数失败：', e)

def apply_mode_params():
    """根据当前 mode 让公共 params 指向对应模式的参数字典，并设 SIGN。"""
    global params, SIGN
    params = params_outer if mode == 'outer' else params_inner
    SIGN = -1 if mode == 'outer' else +1

def load_params_from_file(path):
    global mode
    if not os.path.exists(path):
        return mode
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    def merge(dst, src):
        for k in dst:
            if k in src:
                dst[k] = src[k]
    merge(params_inner, data.get('inner', {}))
    merge(params_outer, data.get('outer', {}))
    saved_mode = data.get('mode', 'inner')
    if saved_mode in ('inner', 'outer'):
        mode = saved_mode
    apply_mode_params()
    return mode

# ---- 派生量（两型共用公式；SIGN 只影响曲线项）----
def E():
    return params['k1'] * params['Rp'] / (params['zc'] + 1)

def P():
    return {'zc': params['zc'], 'zp': params['zc'] + 1, 'e': E(),
            'Rp': params['Rp'], 'rp': params['dp'] / 2, 'drp': params['drp']}

def K2():
    return params['Rp'] * np.sin(np.pi / (params['zc'] + 1)) / (params['dp'] / 2)

# ---- 齿廓缓存 ----
_dataCache = None
_dataKey = ''
def data():
    p = P()
    key = '|'.join([str(p['zc']), '%.3f' % p['e'], str(p['Rp']),
                    '%.2f' % p['rp'], '%.2f' % p['drp']])
    global _dataCache, _dataKey
    if key != _dataKey:
        _dataCache = compute(p)
        _dataKey = key
    return _dataCache

# ---- 齿廓（Onshape drawCycloid，内圈 sign=+1 / 外圈 sign=−1）----
def compute(p):
    N = p['zp'] * 64
    R, n, e = p['Rp'], p['zp'], p['e']
    off = p['rp'] + p['drp']
    t = np.linspace(0, 2 * np.pi, N)
    ct, st = np.cos(t), np.sin(t)
    cnt, snt = np.cos(n * t), np.sin(n * t)
    s = SIGN
    xa = R * ct - s * e * cnt          # SIGN 只管 x 的 e 项
    ya = R * st - e * snt              # y 项恒定
    dxa = -R * st + s * n * e * snt
    dya = R * ct - n * e * cnt
    denom = np.hypot(dxa, dya)
    denom[denom == 0] = 1
    o = s * off / denom                # 偏移方向跟 SIGN（内缩 / 外胀包裹针齿）
    return {'troch': np.stack([xa, ya], axis=1),
            'tooth': np.stack([xa + o * (-dya), ya + o * dxa], axis=1)}

# ---- 摆线（trochoid，针心轨迹）----
def computeTrochoid(e):
    R, n = params['Rp'], params['zc'] + 1
    t = np.linspace(0, 2 * np.pi, n * 64)
    return np.stack([R * np.cos(t) - SIGN * e * np.cos(n * t),
                     R * np.sin(t) - e * np.sin(n * t)], axis=1)

# ---- 位姿 ----
# 内摆：偏心公转（输入）+ 反向自转（输出 = −φ/zc）
def pose():
    e = E()
    return {'Cx': e * np.cos(phi), 'Cy': e * np.sin(phi), 'th': -phi / params['zc']}

# 外摆：刚体圆周平动（th=0，中心角=φ + phase）；暂停时停在静态啮合位
def memberPose(phase):
    e = E()
    ang = (phi + phase) if playing else phase
    return {'Cx': SIGN * e * np.cos(ang), 'Cy': SIGN * e * np.sin(ang), 'th': 0}

# 外摆针齿 = 输出：转 −φ/zp（减速比 1:zp）
def pinAng(p):
    return -phi / p['zp']

# ---- 按给定偏心距 e 和侧隙 drpVal 计算齿廓点 ----
def computeToothAt(e, drpVal=0.0):
    R, n = params['Rp'], params['zc'] + 1
    off = params['dp'] / 2 + drpVal
    t = np.linspace(0, 2 * np.pi, n * 64)
    ct, st = np.cos(t), np.sin(t)
    cnt, snt = np.cos(n * t), np.sin(n * t)
    s = SIGN
    xa = R * ct - s * e * cnt
    ya = R * st - e * snt
    dxa = -R * st + s * n * e * snt
    dya = R * ct - n * e * cnt
    denom = np.hypot(dxa, dya)
    denom[denom == 0] = 1
    o = s * off / denom
    return np.stack([xa + o * (-dya), ya + o * dxa], axis=1)


# ---- 配色（内摆绿 / 外摆紫）：蓝=输入 / 橙=输出，两型语义一致 ----
INNER_C = {
    'green': (0.10, 0.62, 0.31),
    'pinFill': (0, 0, 0, 0.06), 'pinStroke': (0, 0, 0, 0.28),
    'wPin': '#e67e22', 'wPinStroke': '#d35400',
    'holeStroke': (0, 0, 0, 0.30),
    'input': '#4a9eff', 'inputSoft': (0.29, 0.62, 1.0, 0.40),
    'faint': (0, 0, 0, 0.18), 'label': (0, 0, 0, 0.45),
}
OUTER_C = {
    'member': (0.486, 0.227, 0.929),       # #7c3aed 片1 紫
    'm2': (0.145, 0.388, 0.922),           # #2563eb 片2 蓝
    'm3': (0.020, 0.588, 0.412),           # #059669 片3 绿
    'pinFill': '#e67e22', 'pinStroke': '#d35400',
    'input': '#4a9eff',
    'faint': (0, 0, 0, 0.18), 'label': (0, 0, 0, 0.45),
}

# ---- 中文字体：扫描常见系统 CJK 字体并按文件注册到 matplotlib（.ttc 需显式 addfont）----
from matplotlib import rcParams, font_manager as fm

def _setup_cjk_font():
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        'C:/Windows/Fonts/msyh.ttc',
        'C:/Windows/Fonts/simhei.ttf',
        'C:/Windows/Fonts/simsun.ttc',
        '/usr/share/fonts/truetype/arphic/uming.ttc',
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                fm.fontManager.addfont(p)
        except Exception:
            pass

    def score(f):
        n = f.name or ''
        s = 0
        if 'SC' in n or 'CN' in n or 'CJK' in n:
            s += 3
        if any(k in n for k in ('Hei', 'WenQuanYi', 'YaHei', 'SimHei', 'PingFang')):
            s += 2
        if 'Sans' in n:
            s += 1
        return s

    best = sorted(fm.fontManager.ttflist, key=score, reverse=True)
    fam = next((f.name for f in best if score(f) >= 3), None)
    if fam is None:
        fam = next((f.name for f in best if score(f) >= 2), None)
    if fam:
        rcParams['font.family'] = 'sans-serif'
        rcParams['font.sans-serif'] = [fam] + list(rcParams['font.sans-serif'])
        return fam
    return None

_setup_cjk_font()

INNER_FORM = [
    ('针齿数 zc', 'zc', 5, 50, 1, 0, True),
    ('短幅系数 K₁', 'k1', 0.20, 0.95, 0.01, 2, False),
    ('销布置圆 Rp', 'Rp', 8, 40, 0.5, 1, False),
    ('针销直径 dp', 'dp', 1, 6, 0.1, 1, False),
    ('齿侧间隙 drp', 'drp', 0, 1.0, 0.01, 2, False),
    ('W 销数 nw', 'nw', 4, 12, 1, 0, True),
    ('W 销直径 dw', 'dw', 1, 6, 0.1, 1, False),
    ('W 分布圆 Rw', 'Rw', 5, 25, 0.5, 1, False),
    ('偏心套半径 eccR', 'eccR', 2, 15, 0.5, 1, False),
    ('运转速度 speed', 'speed', 0.1, 5.0, 0.1, 1, False),
]
OUTER_FORM = [
    ('针齿数 zc', 'zc', 5, 30, 1, 0, True),
    ('短幅系数 K₁', 'k1', 0.20, 0.95, 0.01, 2, False),
    ('销布置圆 Rp', 'Rp', 8, 40, 0.5, 1, False),
    ('针销直径 dp', 'dp', 1, 6, 0.1, 1, False),
    ('齿侧间隙 drp', 'drp', 0, 1.0, 0.01, 2, False),
    ('枢纽距 din', 'din', 10, 200, 1, 1, False),
    ('面板半径 capR', 'capR', 8, 45, 1, 1, False),
    ('偏心套半径 eccR', 'eccR', 1, 30, 0.5, 1, False),
    ('运转速度 speed', 'speed', 0.1, 5.0, 0.1, 1, False),
]


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('摆线针轮减速器 · 原理演示（内摆 / 外摆）')
        self.resize(1240, 920)
        try:
            load_params_from_file(param_file())      # 重开恢复上次参数
        except Exception as e:
            print('读取上次参数失败：', e)

        self.figure = Figure(figsize=(6, 6), dpi=100)
        self.figure.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_aspect('equal')
        self.ax.axis('off')
        self.canvas = FigureCanvasQTAgg(self.figure)

        central = QWidget()
        self.setCentralWidget(central)
        h = QHBoxLayout(central)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(8)
        h.addWidget(self.canvas, stretch=1)
        h.addWidget(self.build_panel())

        self._fit_limits()
        self.draw_canvas()

        self.timer = QTimer(self)
        self.timer.start(15)
        self.timer.timeout.connect(self.tick)

    # ---- 右侧参数面板 ----
    def build_panel(self):
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(8, 8, 8, 8)

        title = QLabel('摆线针轮减速器 · 原理演示')
        title.setStyleSheet('font-size:15px;font-weight:bold;')
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        self.mode_group = QButtonGroup(self)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self.rb_inner = QRadioButton('内摆线减速器')
        self.rb_outer = QRadioButton('外摆线减速器')
        self.mode_group.addButton(self.rb_inner, 0)
        self.mode_group.addButton(self.rb_outer, 1)
        self.rb_inner.setChecked(mode == 'inner')
        self.rb_outer.setChecked(mode == 'outer')
        rl.addWidget(self.rb_inner)
        rl.addWidget(self.rb_outer)
        rl.addStretch(1)
        v.addWidget(row)
        self.mode_group.buttonClicked[int].connect(self.on_mode)

        self.ratio_label = QLabel()
        self.ratio_label.setStyleSheet('color:#4a9eff;font-weight:bold;')
        self.ratio_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.ratio_label)

        self.k2_label = QLabel()
        self.k2_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.k2_label)

        v.addSpacing(6)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFrameShadow(QFrame.Sunken)
        v.addWidget(sep)

        # 派生计算量
        self.derived_box = QWidget()
        self.derived_v = QVBoxLayout(self.derived_box)
        self.derived_v.setContentsMargins(8, 4, 8, 4)
        self.derived_v.setSpacing(2)
        self.derived_labels = []
        for _ in range(12):
            lab = QLabel()
            lab.setTextFormat(Qt.RichText)
            self.derived_labels.append(lab)
            self.derived_v.addWidget(lab)
        v.addWidget(self.derived_box)

        self.form_widgets = {}
        fw = QWidget(); self.inner_form = QFormLayout(fw)
        self.inner_form.setLabelAlignment(Qt.AlignRight); self.inner_form.setSpacing(6)
        self.inner_form.setVerticalSpacing(3)
        fw2 = QWidget(); self.outer_form = QFormLayout(fw2)
        self.outer_form.setLabelAlignment(Qt.AlignRight); self.outer_form.setSpacing(6)
        self.outer_form.setVerticalSpacing(3)
        self.sp = {'inner': {}, 'outer': {}}
        for spec in INNER_FORM:
            spin = self._add_spin(self.inner_form, *spec)
            self.sp['inner'][spec[1]] = spin
        for spec in OUTER_FORM:
            spin = self._add_spin(self.outer_form, *spec)
            self.sp['outer'][spec[1]] = spin
        self.inner_form_w = fw
        self.outer_form_w = fw2
        v.addWidget(fw)
        v.addWidget(fw2)

        self.dbl_box = QCheckBox('双摆线盘（叠装 180° 相差）')
        self.dbl_box.setChecked(params['dbl'])
        self.dbl_box.toggled.connect(self.on_toggle_generic)
        v.addWidget(self.dbl_box)

        self.stack_box = QCheckBox('三片叠装（120° 相位，动平衡）')
        self.stack_box.setChecked(params['stack'])
        self.stack_box.toggled.connect(self.on_toggle_generic)
        v.addWidget(self.stack_box)
        # 只显示当前模式对应的表单与开关（避免同时出现两套编辑框）
        self.inner_form_w.setVisible(mode == 'inner')
        self.outer_form_w.setVisible(mode == 'outer')
        self.dbl_box.setVisible(mode == 'inner')
        self.stack_box.setVisible(mode == 'outer')

        v.addSpacing(8)
        self.play_btn = QPushButton('▶ 开始动画')
        self.play_btn.setMinimumHeight(30)
        self.play_btn.clicked.connect(self.on_play)
        v.addWidget(self.play_btn)

        reset_btn = QPushButton('复位')
        reset_btn.clicked.connect(self.on_reset)
        v.addWidget(reset_btn)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        save_btn = QPushButton('保存参数')
        save_btn.clicked.connect(self.on_save)
        load_btn = QPushButton('导入参数')
        load_btn.clicked.connect(self.on_load)
        bl.addWidget(save_btn)
        bl.addWidget(load_btn)
        v.addWidget(btn_row)

        v.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(panel)
        scroll.setFixedWidth(340)
        return scroll

    # ---- 参数行（数值框），修改即触发实时刷新 ----
    def _add_spin(self, form, label, key, vmin, vmax, step, dec, int_mode):
        if int_mode:
            spin = NoWheelSpinBox()
            spin.setRange(int(vmin), int(vmax))
            spin.setValue(int(params[key]))
        else:
            spin = NoWheelDoubleSpinBox()
            spin.setRange(vmin, vmax)
            spin.setSingleStep(step)
            spin.setDecimals(dec)
            spin.setValue(params[key])
        spin.valueChanged.connect(lambda v, k=key: self.on_param(k, v))
        form.addRow(label, spin)
        return spin

    # ---- 内摆 / 外摆切换 ----
    def on_mode(self, idx):
        global mode, phi
        new_mode = 'outer' if idx == 1 else 'inner'
        if new_mode == mode:
            return
        apply_mode_params()                 # 先用旧 mode 的当前值刷新对应参数字典
        mode = new_mode
        apply_mode_params()                 # params 指向新模式的字典 + SIGN
        phi = 0.0
        # 同步当前模式控件到已记忆的参数
        for key, spin in self.sp[mode].items():
            if isinstance(spin, QSpinBox):
                spin.setValue(int(params[key]))
            else:
                spin.setValue(params[key])
        self.inner_form_w.setVisible(mode == 'inner')
        self.outer_form_w.setVisible(mode == 'outer')
        self.dbl_box.setVisible(mode == 'inner')
        self.stack_box.setVisible(mode == 'outer')
        self.dbl_box.setChecked(params['dbl'])
        self.stack_box.setChecked(params['stack'])
        self.update_labels()
        self._fit_limits()
        self.draw_canvas()

    def on_toggle_generic(self, checked):
        # 保持当前模式对应的开关与参数一致
        if self.sender() is self.dbl_box:
            params['dbl'] = checked
        else:
            params['stack'] = checked
        self.draw_canvas()

    def on_param(self, key, val):
        params[key] = val
        self.update_labels()
        self._fit_limits()
        self.draw_canvas()

    def on_play(self):
        global playing
        playing = not playing
        self.play_btn.setText('⏸ 暂停' if playing else '▶ 开始动画')

    def on_reset(self):
        global phi, playing
        phi = 0.0
        playing = False
        self.play_btn.setText('▶ 开始动画')
        self.draw_canvas()

    # ---- 保存 / 导入参数 ----
    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, '保存参数到文件',
                                              param_file(), 'JSON 文件 (*.json)')
        if path:
            save_params_to_file(path)

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入参数文件',
                                              '', 'JSON 文件 (*.json)')
        if path:
            try:
                load_params_from_file(path)
            except Exception as e:
                print('导入参数失败：', e)
                return
            self.sync_ui_from_params()
            self.update_labels()
            self._fit_limits()
            self.draw_canvas()

    def sync_ui_from_params(self):
        """将全局 params/mode 同步到界面控件（模式切换、导入、重开恢复时调用）。"""
        self.rb_inner.setChecked(mode == 'inner')
        self.rb_outer.setChecked(mode == 'outer')
        for key, spin in self.sp[mode].items():
            if isinstance(spin, QSpinBox):
                spin.setValue(int(params[key]))
            else:
                spin.setValue(params[key])
        self.inner_form_w.setVisible(mode == 'inner')
        self.outer_form_w.setVisible(mode == 'outer')
        self.dbl_box.setVisible(mode == 'inner')
        self.stack_box.setVisible(mode == 'outer')
        self.dbl_box.setChecked(params['dbl'])
        self.stack_box.setChecked(params['stack'])

    def closeEvent(self, event):
        try:
            save_params_to_file(param_file())      # 关闭前自动保存，下次启动恢复
        except Exception:
            pass
        super().closeEvent(event)

    def update_labels(self):
        zp = params['zc'] + 1
        k2 = K2()
        if mode == 'inner':
            self.ratio_label.setText('减速比  1 : %d（zp = %d）' % (params['zc'], zp))
        else:
            self.ratio_label.setText('减速比  1 : %d（输出 = 针齿）' % zp)
        self.k2_label.setText('K₁ = %.2f    K₂ = %.2f   %s'
                              % (params['k1'], k2, '✓ 针不重叠' if k2 > 1 else '⚠ 针齿干涉'))
        self.k2_label.setStyleSheet('color:#e67e22' if k2 <= 1 else '')
        self._refresh_derived()

    # ---- 派生计算量（列出计算式与实数值）----
    def _derived_rows(self):
        zp = params['zc'] + 1
        e = E()
        rp = params['dp'] / 2
        b = params['Rp'] / zp
        off = rp + params['drp']
        rows = [
            ('针齿数 zp',    '<b>zp = zc + 1</b> = %d' % zp),
            ('滚圆半径 b',   '<b>b = Rp/zp</b> = %.2f mm' % b),
            ('偏心距 e',     '<b>e = K1·Rp/zp</b> = %.2f mm' % e),
            ('针齿半径 rp',  '<b>rp = dp/2</b> = %.2f mm' % rp),
            ('齿廓偏移 off', '<b>off = rp + drp</b> = %.2f mm' % off),
            ('针径系数 K2',  '<b>K2 = Rp·sin(π/zp)/rp</b> = %.2f' % K2()),
        ]
        if mode == 'inner':
            wR = params['dw'] / 2
            holeR = wR + e
            rows.insert(1, ('减速比 i', '<b>i = zc</b> = 1 : %d' % params['zc']))
            rows += [
                ('W 销半径 wR',  '<b>wR = dw/2</b> = %.2f mm' % wR),
                ('W 孔半径 holeR', '<b>holeR = wR + e</b> = %.2f mm' % holeR),
            ]
        else:
            lobes = params['zc'] + 2
            rows.insert(1, ('减速比 i', '<b>i = zp</b> = 1 : %d' % zp))
            rows += [
                ('凸瓣数 lobes', '<b>lobes = zc + 2</b> = %d %s'
                 % (lobes, '✓ 三片均布' if lobes % 3 == 0 else '⚠ 非3倍，三片干涉')),
                ('枢纽距 din',  '<b>din</b> = %.1f mm' % params['din']),
                ('面板半径 capR','<b>capR</b> = %.1f mm' % params['capR']),
                ('偏心圆半径',  '<b>eccR</b> = %.1f mm' % params['eccR']),
                ('输出角速度',  '<b>ω = −φ/zp</b>（针齿慢转）'),
            ]
        return rows

    def _refresh_derived(self):
        rows = self._derived_rows()
        for i, lab in enumerate(self.derived_labels):
            if i < len(rows):
                name, txt = rows[i]
                lab.setText('<span style="color:#666">%s</span>&nbsp;&nbsp;%s' % (name, txt))
                lab.setVisible(True)
            else:
                lab.setText('')
                lab.setVisible(False)

    # ---- 画布 ----
    def _fit_limits(self):
        if mode == 'inner':
            base = max(params['Rp'], params['Rw'])
            m = base + params['dp'] / 2 + 5.0
            self.ax.set_xlim(-m, m)
            self.ax.set_ylim(-m, m)
        else:
            e = E()
            half = max(params['Rp'] + params['dp'] / 2, params['capR'] + e) + 4
            self.ax.set_xlim(-half, half)
            # 胶囊全程撑满：A 中心 ±e，面板顶部到 +capR+e，底部到 −(din+capR+e)
            self.ax.set_ylim(-(params['din'] + params['capR'] + e) - 6, half + 2)

    def pin_r(self, mm):
        return max(mm, 0.16)

    def col(self):
        return INNER_C if mode == 'inner' else OUTER_C

    def dashed_circle(self, x, y, r, color, lw=1.4, dashes=(6, 6)):
        th = np.linspace(0, 2 * np.pi, 240)
        self.ax.plot(x + r * np.cos(th), y + r * np.sin(th),
                     color=color, lw=lw, ls=(0, dashes))
        self.ax.set_aspect('equal')

    def solid_circle(self, x, y, r, color, lw=1.4):
        th = np.linspace(0, 2 * np.pi, 240)
        self.ax.plot(x + r * np.cos(th), y + r * np.sin(th), color=color, lw=lw)

    def fill_circle(self, x, y, r, color, alpha=None):
        th = np.linspace(0, 2 * np.pi, 240)
        self.ax.fill(x + r * np.cos(th), y + r * np.sin(th), color=color, alpha=alpha)

    def draw_path(self, pts, pp, color, lw, alpha=1.0):
        c, s = np.cos(pp['th']), np.sin(pp['th'])
        wx = pts[:, 0] * c - pts[:, 1] * s + pp['Cx']
        wy = pts[:, 0] * s + pts[:, 1] * c + pp['Cy']
        self.ax.plot(wx, wy, color=color, lw=lw, alpha=alpha)

    # ================= 内摆线实现 =================
    def draw_inner(self):
        ax = self.ax
        C = INNER_C
        p = P()
        pp = pose()

        self.dashed_circle(0, 0, E(), C['faint'], 1, dashes=(3, 4))   # 公转轨迹
        self.dashed_circle(0, 0, p['Rp'], C['faint'], 1.4)            # 针齿中心圆
        for i in range(p['zp']):                                       # 针齿（固定）
            a = i / p['zp'] * 2 * np.pi
            ax.add_patch(Circle((p['Rp'] * np.cos(a), p['Rp'] * np.sin(a)),
                                self.pin_r(p['rp']),
                                facecolor=C['pinFill'], edgecolor=C['pinStroke'], lw=1.1))
        if params['dbl']:                                              # 双盘：第二片（淡绿下层）
            pp2 = {'Cx': -pp['Cx'], 'Cy': -pp['Cy'], 'th': pp['th'] - np.pi / params['zc']}
            self.draw_path(data()['tooth'], pp2, C['green'], 2, 0.35)
        self.draw_path(data()['tooth'], pp, C['green'], 2, 1)          # 主齿廓
        self.dashed_circle(0, 0, params['Rw'], (0.90, 0.49, 0.13, 0.4), 1.2, dashes=(5, 5))
        if params['dbl']:                                              # 双盘偏心（淡蓝下层）
            px2, py2 = -pp['Cx'], -pp['Cy']
            self.solid_circle(px2, py2, params['eccR'], C['inputSoft'], 1.4)
            ax.plot([px2, px2 + params['eccR'] * np.cos(phi + np.pi)],
                    [py2, py2 + params['eccR'] * np.sin(phi + np.pi)],
                    color=C['inputSoft'], lw=1.4)
        self.solid_circle(pp['Cx'], pp['Cy'], params['eccR'], C['input'], 1.6)  # 偏心套
        ax.plot([pp['Cx'], pp['Cx'] + params['eccR'] * np.cos(phi)],
                [pp['Cy'], pp['Cy'] + params['eccR'] * np.sin(phi)],
                color=C['input'], lw=1.6)

        wR = params['dw'] / 2
        holeR = wR + E()
        if params['dbl']:                                              # 双盘 W 孔（淡，下层）
            pp2 = {'Cx': -pp['Cx'], 'Cy': -pp['Cy'], 'th': pp['th'] - np.pi / params['zc']}
            for i in range(params['nw']):
                a = i / params['nw'] * 2 * np.pi + pp2['th'] + np.pi / params['zc']
                hx = pp2['Cx'] + params['Rw'] * np.cos(a)
                hy = pp2['Cy'] + params['Rw'] * np.sin(a)
                ax.add_patch(Circle((hx, hy), holeR, fill=False,
                                    edgecolor=(0, 0, 0, 0.14), lw=1.1))
        for i in range(params['nw']):                                  # W 孔
            a = i / params['nw'] * 2 * np.pi + pp['th']
            hx = pp['Cx'] + params['Rw'] * np.cos(a)
            hy = pp['Cy'] + params['Rw'] * np.sin(a)
            ax.add_patch(Circle((hx, hy), holeR, fill=False,
                                edgecolor=C['holeStroke'], lw=1.1))
        for i in range(params['nw']):                                  # W 销 + 箭头
            a = i / params['nw'] * 2 * np.pi + pp['th']
            px = params['Rw'] * np.cos(a)
            py = params['Rw'] * np.sin(a)
            r = self.pin_r(wR)
            ax.add_patch(Circle((px, py), r, facecolor=C['wPin'],
                                edgecolor=C['wPinStroke'], lw=1))
            ux, uy = np.sin(a), np.cos(a)
            L = r * 0.85
            hd = max(0.12, r * 0.45)
            hx = px + ux * L
            hy = py + uy * L
            ax.plot([px - ux * L, hx], [py - uy * L, hy], color='white', lw=1.2)
            ax.plot([hx, hx - ux * hd - uy * hd * 0.85],
                    [hy, hy - uy * hd + ux * hd * 0.85], color='white', lw=1.2)
            ax.plot([hx, hx - ux * hd + uy * hd * 0.85],
                    [hy, hy - uy * hd - ux * hd * 0.85], color='white', lw=1.2)
        ax.add_patch(Circle((0, 0), 2.5, fill=False, edgecolor=C['input'], lw=1.6))
        ax.plot([0, 5 * np.cos(phi)], [0, 5 * np.sin(phi)], color=C['input'], lw=2)

    # ================= 外摆线实现 =================
    def draw_pins_outer(self, p, with_arrows):
        C = OUTER_C
        ang = pinAng(p)
        for i in range(p['zp']):
            a = i / p['zp'] * 2 * np.pi + ang
            x = p['Rp'] * np.cos(a)
            y = p['Rp'] * np.sin(a)
            r = self.pin_r(p['rp'])
            self.ax.add_patch(Circle((x, y), r, facecolor=C['pinFill'],
                                     edgecolor=C['pinStroke'], lw=1.1))
            if with_arrows:
                ux, uy = np.sin(a), np.cos(a)
                L = r * 0.85
                hd = max(0.12, r * 0.45)
                hx = x + ux * L
                hy = y + uy * L
                self.ax.plot([x - ux * L, hx], [y - uy * L, hy], color='white', lw=1.2)
                self.ax.plot([hx, hx - ux * hd - uy * hd * 0.85],
                             [hy, hy - uy * hd + ux * hd * 0.85], color='white', lw=1.2)
                self.ax.plot([hx, hx - ux * hd + uy * hd * 0.85],
                             [hy, hy - uy * hd - ux * hd * 0.85], color='white', lw=1.2)

    def _capsule_outline(self, axc, ay, bx, by, r):
        a_arc = [(axc + r * np.cos(a), ay + r * np.sin(a)) for a in np.linspace(0, np.pi, 48)]
        b_arc = [(bx + r * np.cos(a), by + r * np.sin(a)) for a in np.linspace(np.pi, 2 * np.pi, 48)]
        return np.array(a_arc + [(bx - r, by)] + b_arc + [(axc + r, ay)])

    def draw_member(self, p, phase, col, alpha):
        C = OUTER_C
        pose = memberPose(phase)
        rot = phase / (p['zp'] + 1)                    # 齿廓错位保证三片都啮合
        cr, sr = np.cos(rot), np.sin(rot)
        tooth = computeToothAt(p['e'], params['drp'])
        tx = tooth[:, 0] * cr - tooth[:, 1] * sr + pose['Cx']
        ty = tooth[:, 0] * sr + tooth[:, 1] * cr + pose['Cy']

        r = params['capR']
        eccR = params['eccR']
        ax, ay = pose['Cx'], pose['Cy']                # A=摆线轮中心
        bx, by = pose['Cx'], pose['Cy'] - params['din']  # B=偏心套中心（同偏移平动）

        # 面板 evenodd 挖空：胶囊 ∖ 齿廓内 ∖ 偏心圆内（用白底覆盖镂空）
        cap = self._capsule_outline(ax, ay, bx, by, r)
        self.ax.fill(cap[:, 0], cap[:, 1], color=col, alpha=0.16 * alpha)
        self.ax.fill(tx, ty, color='white')            # 挖齿孔
        self.fill_circle(bx, by, eccR, 'white')        # 挖偏心圆孔
        # 胶囊 / 齿廓 / 偏心圆 轮廓
        self.ax.plot(np.append(cap[:, 0], cap[0, 0]), np.append(cap[:, 1], cap[0, 1]),
                     color=col, lw=1.8, alpha=alpha)
        self.ax.plot(tx, ty, color=col, lw=2.2, alpha=alpha)
        th = np.linspace(0, 2 * np.pi, 240)
        self.ax.plot(bx + eccR * np.cos(th), by + eccR * np.sin(th),
                     color=col, lw=1.6, alpha=alpha * 0.9)

    def draw_outer(self):
        ax = self.ax
        C = OUTER_C
        p = P()

        e = E()
        self.dashed_circle(0, 0, e, C['faint'], 1, dashes=(3, 4))     # A 中心公转轨迹
        members = [(0, C['member'], 0.6), (2 * np.pi / 3, C['m2'], 0.6),
                   (4 * np.pi / 3, C['m3'], 0.6)] if params['stack'] \
            else [(0, C['member'], 1.0)]
        for phase, col, a in members:
            self.draw_member(p, phase, col, a)
        self.draw_pins_outer(p, True)                                  # 针齿输出（最上层）

        pose0 = memberPose(0)                                          # 输入轴心
        ax.add_patch(Circle((0, 0), 2.5, color='#9ca3af', zorder=2))
        in_x, in_y = 0, -params['din']
        in_r = max(2.5, 0.12 * params['Rp'])
        ax.add_patch(Circle((in_x, in_y), in_r, color=C['input'], zorder=2))
        ax.plot([in_x, pose0['Cx']], [in_y, pose0['Cy'] - params['din']],
                color=C['input'], lw=1.4)

    # ---- 渲染 ----
    def draw_canvas(self):
        ax = self.ax
        ax.clear()
        ax.axis('off')
        self._fit_limits()
        if mode == 'inner':
            self.draw_inner()
        else:
            self.draw_outer()
        self.canvas.draw_idle()

    # ---- 动画定时器 ----
    def tick(self):
        if playing:
            global phi
            phi += 0.016 * params['speed']
            self.draw_canvas()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    win = Main()
    win.update_labels()
    win.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()