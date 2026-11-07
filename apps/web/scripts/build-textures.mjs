/**
 * 生成纸张纤维贴图（任务书 §4.6）：public/textures/fiber-{a,b,c}.png
 * 2 位调色板 PNG（透明 + 三级墨色），三张合计 < 20 KB。
 * 纤维 = 随机方向的短弧线 + 稀疏的纸浆颗粒；平铺无缝（坐标取模）。
 * 用法：node scripts/build-textures.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const out = path.resolve(import.meta.dirname, '../public/textures');

function rng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

function crc32(buf) {
  let c, crc = 0xffffffff;
  for (let n = 0; n < buf.length; n++) {
    c = (crc ^ buf[n]) & 0xff;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    crc = (crc >>> 8) ^ c;
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const td = Buffer.concat([Buffer.from(type), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td));
  return Buffer.concat([len, td, crc]);
}

function texture(size, seed, fibers, specks) {
  const r = rng(seed);
  const px = new Uint8Array(size * size);
  const put = (x, y, v) => {
    const i = (((Math.round(y) % size) + size) % size) * size + (((Math.round(x) % size) + size) % size);
    px[i] = Math.max(px[i], v);
  };
  for (let f = 0; f < fibers; f++) {
    let x = r() * size, y = r() * size, a = r() * Math.PI * 2;
    const len = 6 + r() * 22, bend = (r() - 0.5) * 0.18, v = r() < 0.25 ? 2 : 1;
    for (let s = 0; s < len; s++) { put(x, y, v); x += Math.cos(a); y += Math.sin(a); a += bend; }
  }
  for (let s = 0; s < specks; s++) put(r() * size, r() * size, r() < 0.15 ? 3 : r() < 0.5 ? 2 : 1);
  // 2 位深度：每字节 4 像素，每行前一个滤波字节
  const row = size / 4;
  const raw = Buffer.alloc((row + 1) * size);
  for (let y = 0; y < size; y++) {
    raw[y * (row + 1)] = 0;
    for (let x = 0; x < size; x++) raw[y * (row + 1) + 1 + (x >> 2)] |= px[y * size + x] << (6 - (x % 4) * 2);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 2; ihdr[9] = 3; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const plte = Buffer.from([0, 0, 0, 20, 16, 12, 20, 16, 12, 20, 16, 12]);
  const trns = Buffer.from([0, 70, 130, 200]);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr), chunk('PLTE', plte), chunk('tRNS', trns),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })), chunk('IEND', Buffer.alloc(0)),
  ]);
}

let total = 0;
for (const [name, size, seed, fibers, specks] of [['a', 160, 7, 70, 260], ['b', 224, 31, 60, 180], ['c', 128, 101, 40, 340]]) {
  const buf = texture(size, seed, fibers, specks);
  fs.writeFileSync(path.join(out, `fiber-${name}.png`), buf);
  total += buf.length;
  console.log(`fiber-${name}.png`, buf.length, 'bytes');
}
console.log('total', total);
