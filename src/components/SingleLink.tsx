import { ArrowRight, ClipboardPaste, LoaderCircle, X } from 'lucide-react';
import { hostOf, looksLikeMany } from '../lib/links';

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onPasteMany: (text: string) => void;
  busy: boolean;
}

export function SingleLink({ value, onChange, onSubmit, onPasteMany, busy }: Props) {
  const host = /^https?:\/\//i.test(value.trim()) ? hostOf(value.trim()) : '';

  async function pasteFromClipboard() {
    try {
      const text = (await navigator.clipboard.readText()).trim();
      if (!text) return;
      if (looksLikeMany(text)) onPasteMany(text);
      else onChange(text);
    } catch {
      /* Clipboard permission denied: the user can still paste manually. */
    }
  }

  return (
    <form
      className={`slot ${busy ? 'busy' : ''}`}
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label htmlFor="link" className="sr-only">
        Media link
      </label>
      <span className={`slot-host ${host ? 'lit' : ''}`}>{host || 'link'}</span>
      <input
        id="link"
        type="url"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        placeholder="https://… YouTube, X, Instagram, TikTok, Reddit, Vimeo…"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onPaste={(e) => {
          const text = e.clipboardData.getData('text');
          if (looksLikeMany(text)) {
            e.preventDefault();
            onPasteMany(text);
          }
        }}
        autoFocus
      />
      {value ? (
        <button type="button" className="icon-btn" onClick={() => onChange('')} aria-label="Clear link">
          <X size={16} />
        </button>
      ) : (
        <button type="button" className="icon-btn" onClick={pasteFromClipboard} aria-label="Paste from clipboard" title="Paste">
          <ClipboardPaste size={16} />
        </button>
      )}
      <button type="submit" className="go" disabled={busy || !value.trim()}>
        {busy ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}
        {busy ? 'Reading' : 'Fetch'}
      </button>
    </form>
  );
}
