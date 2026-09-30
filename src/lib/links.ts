export const MAX_BATCH = 50;

export interface ParsedLine {
  line: number;
  text: string;
  url: string | null;
  duplicate: boolean;
}

/** Pulls the first http(s) URL out of each non-empty line, flagging junk and repeats. */
export function parseLines(input: string): ParsedLine[] {
  const seen = new Set<string>();
  const parsed: ParsedLine[] = [];
  input.split(/\r?\n/).forEach((raw, index) => {
    const text = raw.trim();
    if (!text) return;
    const match = text.match(/https?:\/\/[^\s<>"']+/i);
    let url: string | null = null;
    if (match) {
      try {
        url = new URL(match[0].replace(/[),.;]+$/, '')).toString();
      } catch {
        url = null;
      }
    }
    const duplicate = url !== null && seen.has(url);
    if (url) seen.add(url);
    parsed.push({ line: index + 1, text, url, duplicate });
  });
  return parsed;
}

export function uniqueUrls(lines: ParsedLine[]): string[] {
  return lines.filter((l) => l.url && !l.duplicate).map((l) => l.url as string);
}

/** Pasting several links into the single-link bar should open the batch composer instead. */
export function looksLikeMany(text: string): boolean {
  return (text.match(/https?:\/\//gi) ?? []).length > 1;
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
