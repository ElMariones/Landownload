import { describe, expect, it } from 'vitest';
import { hostOf, looksLikeMany, parseLines, uniqueUrls } from './links';
import { formatBytes, formatDuration } from './format';

describe('parseLines', () => {
  it('keeps one URL per line, flags junk and duplicates', () => {
    const lines = parseLines(`
      https://www.youtube.com/watch?v=abc
      not a link
      see this: https://x.com/user/status/1).

      https://www.youtube.com/watch?v=abc
    `);
    expect(lines).toHaveLength(4);
    expect(lines[1].url).toBeNull();
    expect(lines[2].url).toBe('https://x.com/user/status/1');
    expect(lines[3].duplicate).toBe(true);
    expect(uniqueUrls(lines)).toEqual(['https://www.youtube.com/watch?v=abc', 'https://x.com/user/status/1']);
  });

  it('detects multi-link pastes', () => {
    expect(looksLikeMany('https://a.com/1 https://b.com/2')).toBe(true);
    expect(looksLikeMany('https://a.com/1')).toBe(false);
  });

  it('reads hosts without www', () => {
    expect(hostOf('https://www.vimeo.com/123')).toBe('vimeo.com');
  });
});

describe('format', () => {
  it('formats sizes and durations', () => {
    expect(formatBytes(1175764531)).toBe('1.1 GB');
    expect(formatBytes(0)).toBe('');
    expect(formatDuration(187)).toBe('3:07');
    expect(formatDuration(3725)).toBe('1:02:05');
  });
});
