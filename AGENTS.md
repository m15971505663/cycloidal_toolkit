# AGENTS.md

## 项目概述

**摆线针轮减速器 · 原理演示** —— 小红书小工具（离线 H5），用 2D canvas 动画演示摆线减速器的工作原理。

纯前端、零运行时依赖、零构建依赖。产物是符合小红书容器规范的 `.zip`，直接上传。

## 技术栈

- 前端：vanilla JS + canvas 2D，无框架、无第三方库
- 构建：`node tools/build.js`（拷贝 src → dist）、`node tools/pack.js`（打 zip + 规范自检）
- 无 npm 依赖（package.json 只有 build/pack 两个脚本）

## 目录结构

```
cycloidal_toolkit/
├── src/               # 源码（唯一需要改的地方）
│   ├── index.html     # 入口（脚本外置，viewport-fit=cover）
│   ├── style.css      # v7 浅灰玻璃风视觉
│   └── main.js        # 全部逻辑：绘制 + 动画 + 交互 + 参数
├── tools/
│   ├── build.js       # src → dist
│   └── pack.js        # dist → cycloidal_cycloid.zip + 自检
├── archive/           # 桌面端历史版本（数学来源，勿改）
├── scheme/            # 参数参考 JSON
├── docs/preview.png   # 预览图
└── dist/              # 构建产物（git 忽略）
```

## 开发命令

```bash
npm run build   # src → dist
npm run pack    # dist → cycloidal_cycloid.zip + 自检
```

本地预览：`dist/` 下起静态 server（注意要 no-cache，否则浏览器缓存旧版）。

## 核心约定（重要）

### 1. 小红书容器规范
- 脚本必须外置（`<script src>`），禁止内联 `<script>`、`onclick=`、`eval`、`new Function`、`fetch`
- 无外部资源（字体/图片/CDN 全无），全部打进 zip
- `index.html` 必须在 zip 根目录
- 文件类型白名单：`.html/.css/.js`（+图片/字体/json）
- `npm run pack` 自带规范自检，全绿才算合规

### 2. 5 阶段分步设计器（核心交互）
控制面板左右滑动，一屏一阶段，画布随阶段展示不同重点：

| 阶段 | 名称 | 参数 | 画布 |
|---|---|---|---|
| ① | 销布置 | zc / Rp / dp | 虚线圆 + 销钉（无摆线）|
| ② | 摆线生成 | K₁（e 派生）| 滚圆滚动画出摆线 |
| ③ | 啮合修形 | drp | 齿廓贴销钉、间隙 |
| ④ | W 机构（静止）| nW / dw / Rw / eccR | 偏心套 + W 销/孔 |
| ⑤ | 运转验证（运动）| speed | 偏心公转 + 自转 + 表盘 |

### 3. 摆线数学（物理关系，别搞混）
- **摆线（trochoid）** = 针心轨迹 = 滚圆上离圆心 e 的点的轨迹：
  `x = Rp·cos t − e·cos(zp·t)`，绕销钉圆波动 ±e
- **齿廓（tooth）** = 摆线沿法向**向内**偏移 `rp + drp`（内缩，产生间隙）
- `e = K₁·Rp/zp`（短幅系数 K₁ 派生），`zp = zc + 1`
- K₁ < 1 短幅必须（否则齿根尖角），K₂ = Rp·sin(π/zp)/rp > 1（针不重叠）
- 阶段② 展示**摆线**（trochoid），阶段③ 才展示**齿廓**（tooth）——两者差 rp+drp 偏移

### 4. 缩放体系（三个层次，别混）
- `baseScale`：mm→px 基础（仅窗口变化 fit 一次，调参不重算 → 销钉视觉恒定）
- `zoom`：手势缩放（双指捏合 / 滚轮，0.35~3.5）
- `view.zoom / view.cx / view.cy`：拖 K₁/drp 时的**聚焦**缩放平移（focus.t 过渡）
- 综合缩放 `vs() = scale() * view.zoom`

### 5. ②↔③ 过渡动画（三节点镜像）
```
前进 ②→③：不透明度(morphT) → 位移(eccCur) → 缩放(drpCur)
后退 ③→②：缩放(drpCur) → 位移(eccCur) → 不透明度(morphT)
```
- `morphT`：摆线亮↔齿廓亮的透明度互换
- `eccCur`：偏心距过渡（齿廓向右贴销钉）
- `drpCur`：齿侧间隙过渡（齿廓内缩）
- 阶段④ 静止（viewPose 返回偏心 +e 不自转），阶段⑤ 才用 pose() 运转

### 6. 参数（state 对象，全部在 main.js 顶部）
`zc=14, k1=0.75, Rp=16, dp=2, drp=0.2, nw=6, dw=2, Rw=10, eccR=7, speed=1`

直径语义：dp/dw 是**直径**（购买规格），内部 `/2` 换算半径。

## 改动建议

- 改视觉 → `src/style.css`
- 改逻辑/动画/参数 → `src/main.js`（单文件，约 730 行，函数式组织）
- 改结构/文案 → `src/index.html`
- 改完必须 `npm run pack` 自检 + 在 dist 起 no-cache server 浏览器验证（注意浏览器缓存）
