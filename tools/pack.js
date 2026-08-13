#!/usr/bin/env node
/**
 * 打包 + 自检：src → dist → zip（index.html 在 zip 根目录）
 * 自检：入口位置 / 无内联脚本 / 无行内事件 / 文件类型白名单 / 无外部引用 / 体积
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'src');
const DIST = path.join(ROOT, 'dist');
const OUT = path.join(ROOT, 'cycloidal_cycloid.zip');

function copy(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

// 纯 Node 解析 zip 中央目录，取全部条目名（跨平台，不依赖 zip/unzip/tar）
function zipEntryNames(buf) {
  let e = -1;                                   // EOCD 记录
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 65536); i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { e = i; break; }
  }
  if (e < 0) return null;
  const count = buf.readUInt16LE(e + 10);
  let off = buf.readUInt32LE(e + 16);
  const names = [];
  for (let k = 0; k < count; k++) {
    if (off + 46 > buf.length || buf.readUInt32LE(off) !== 0x02014b50) break;
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const cmtLen = buf.readUInt16LE(off + 32);
    names.push(buf.toString('utf8', off + 46, off + 46 + nameLen));
    off += 46 + nameLen + extraLen + cmtLen;
  }
  return names;
}

function main() {
  // 组装 dist（同步最新 src）
  fs.rmSync(DIST, { recursive: true, force: true });
  fs.mkdirSync(DIST, { recursive: true });
  for (const f of fs.readdirSync(SRC)) {
    copy(path.join(SRC, f), path.join(DIST, f));
  }

  // 打 zip：压缩 dist「内容」，index.html 必须是根条目
  // Windows 无 zip 命令，用系统自带 bsdtar（-a 按扩展名选 zip 格式）。
  // 注意：不能打包 "."（bsdtar 会给条目加 "./" 前缀，平台校验要求恰为 "index.html"），
  // 必须显式列出文件名。
  if (process.platform === 'win32') {
    const bsdtar = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe');
    const files = fs.readdirSync(DIST).filter(f => !f.startsWith('.'));
    execSync(`"${bsdtar}" -a -c -f "${OUT}" ${files.map(f => `"${f}"`).join(' ')}`,
             { cwd: DIST, stdio: 'inherit' });
  } else {
    execSync(`cd "${DIST}" && zip -r "${OUT}" . -x '*.DS_Store' -x '__MACOSX*'`, { stdio: 'inherit' });
  }

  // ──────── 自检 ────────
  console.log('\n════════ 自检 ════════');
  let pass = true;
  const chk = (ok, msg) => { pass = pass && ok; console.log(`${ok ? '✓' : '✗'} ${msg}`); };

  chk(fs.existsSync(path.join(DIST, 'index.html')), 'index.html 在 zip 根目录');

  // 条目名精确校验：必须是 "index.html"，不能带 "./" 前缀或套子目录
  const names = zipEntryNames(fs.readFileSync(OUT));
  chk(Array.isArray(names) && names.includes('index.html'),
      'zip 条目名恰为 index.html（实际: ' + (names ? names.join(', ') : '解析失败') + '）');

  const html = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8');
  const hasInlineScript = /<script(?![^>]*\bsrc=)[^>]*>[\s\S]*<\/script>/.test(html);
  chk(!hasInlineScript, '无内联 <script>');
  chk(!/\son\w+\s*=/.test(html), '无行内事件 onclick= 等');
  chk(!/https?:\/\//.test(html), '无外部 URL 引用');

  const js = fs.readFileSync(path.join(DIST, 'main.js'), 'utf8');
  chk(!/\beval\s*\(|\bnew\s+Function\s*\(|fetch\s*\(/.test(js), 'JS 无 eval / new Function / fetch');

  const allFiles = [];
  (function walk(dir) {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) walk(full);
      else allFiles.push(path.relative(DIST, full));
    }
  })(DIST);
  const allowed = ['.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.woff', '.woff2', '.json'];
  const bad = allFiles.filter(f => !allowed.includes(path.extname(f).toLowerCase()));
  chk(bad.length === 0, '文件类型白名单' + (bad.length ? '：' + bad.join(', ') : ''));
  chk(!allFiles.some(f => /\.map$/.test(f) || f.includes('.DS_Store')), '无 *.map / .DS_Store');

  const zipSize = fs.statSync(OUT).size;
  chk(zipSize < 2 * 1024 * 1024, `体积 ${(zipSize / 1024).toFixed(0)} KB < 2MB`);

  console.log(`\n${pass ? '✓ 全部通过' : '✗ 存在未通过项'}`);
  console.log(`zip:  ${OUT}`);
  console.log(`文件: ${allFiles.join(', ')}`);
  process.exit(pass ? 0 : 1);
}

main();
