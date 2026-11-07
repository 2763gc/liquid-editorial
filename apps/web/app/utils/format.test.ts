import { describe, expect, it } from 'vitest';
import { compactNumber, dotDate, fileSize, issueNo, plainText, timeAgo } from './format';

describe('timeAgo', () => {
  const now = Date.parse('2026-10-22T12:00:00Z');
  it('buckets recent times', () => {
    expect(timeAgo('2026-10-22T11:59:30+00:00', now)).toBe('刚刚');
    expect(timeAgo('2026-10-22T11:40:00+00:00', now)).toBe('20 分钟前');
    expect(timeAgo('2026-10-22T09:00:00Z', now)).toBe('3 小时前');
    expect(timeAgo('2026-10-19T12:00:00', now)).toBe('3 天前');
  });
  it('falls back to a dotted date after 30 days and handles empties', () => {
    expect(timeAgo('2026-08-01T00:00:00Z', now)).toBe('2026.08.01');
    expect(timeAgo(null, now)).toBe('');
    expect(timeAgo('not a date', now)).toBe('');
  });
});

describe('fileSize', () => {
  it('formats bytes, kilobytes and megabytes', () => {
    expect(fileSize(251)).toBe('251 B');
    expect(fileSize(2048)).toBe('2.0 KB');
    expect(fileSize(51200)).toBe('50 KB');
    expect(fileSize(3 * 1024 * 1024)).toBe('3.0 MB');
  });
});

describe('dotDate', () => {
  it('formats ISO timestamps as dotted dates', () => {
    expect(dotDate('2026-08-27T10:00:00+00:00')).toBe('2026.08.27');
  });
  it('returns an empty string for missing values', () => {
    expect(dotDate(null)).toBe('');
    expect(dotDate(undefined)).toBe('');
  });
});

describe('issueNo', () => {
  it('pads to three digits by default', () => {
    expect(issueNo(1)).toBe('001');
    expect(issueNo(null)).toBe('000');
    expect(issueNo(7, 2)).toBe('07');
  });
});

describe('plainText', () => {
  it('drops GitHub alert markers and literal \\n sequences', () => {
    expect(plainText('为什么 [!NOTE] Rust 标准库\\n\\n仅定义了 Future')).toBe('为什么 Rust 标准库 仅定义了 Future');
  });
  it('removes code fences and keeps inline code and link text', () => {
    expect(plainText('看 `poll` 与 [文档](https://x.dev)\n```rust\nfn main() {}\n```\n结束')).toBe('看 poll 与 文档 结束');
  });
  it('strips heading, list and emphasis markers', () => {
    expect(plainText('## 标题\n- **粗体** 条目\n> 引用')).toBe('标题 粗体 条目 引用');
  });
  it('truncates with an ellipsis when max is given', () => {
    expect(plainText('一二三四五六', 4)).toBe('一二三四…');
    expect(plainText('一二三', 4)).toBe('一二三');
  });
});

describe('compactNumber', () => {
  it('uses grouping below ten thousand and 万 above', () => {
    expect(compactNumber(1840)).toBe('1,840');
    expect(compactNumber(12345)).toBe('1.2 万');
    expect(compactNumber(250000)).toBe('25 万');
  });
});
