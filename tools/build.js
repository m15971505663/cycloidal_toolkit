#!/usr/bin/env node
/**
 * 构建：把 src/ 拷贝到 dist/（零依赖，无打包器——项目无第三方库）
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'src');
const DIST = path.join(ROOT, 'dist');

function main() {
  fs.rmSync(DIST, { recursive: true, force: true });
  fs.mkdirSync(DIST, { recursive: true });
  for (const f of fs.readdirSync(SRC)) {
    fs.copyFileSync(path.join(SRC, f), path.join(DIST, f));
    const kb = (fs.statSync(path.join(DIST, f)).size / 1024).toFixed(1);
    console.log(`✓ ${f}  ${kb} KB`);
  }
  console.log('✓ 构建完成');
}

main();
