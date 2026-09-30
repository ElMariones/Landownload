# Landownload

A private, ad-free media downloader. Paste a link from YouTube, X, Instagram, TikTok, Reddit or [a thousand other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), get a preview, and pick any quality the source offers, up to the original upload. There are no quality caps, trackers, or pop-ups.

- **Every quality**: all renditions are listed with resolution, fps, codec and size. Silent high-res streams are merged with the best audio automatically when FFmpeg is installed. There are also audio-only tracks and a 320 kbps MP3 conversion.
- **Images and galleries**: posts with several videos or photos list every item, plus an "All · ZIP" option. Photos download in their original resolution.
- **Batch → ZIP**: paste up to 50 links, one per line. Each one is fetched at its highest quality and packed into a single ZIP. Broken links don't stop the batch; they are listed in `failed-links.txt` inside the archive.
- **X / Twitter**: posts that X hides from logged-out visitors fall back to the public FxTwitter API, so they still download without cookies.
- **The tray**: live progress, speed and ETA, cancel, and download history that survives restarts. Finished files save automatically and are deleted from the server after 48 hours.
- **Paste anywhere**: press `Ctrl+V` anywhere on the page to fetch a link. Pasting several links at once opens the batch composer.
- **Use it from your phone**: the interface is published on GitHub Pages and connects to your own server with an access key.

## Requirements

| Tool | Why | Get it |
| --- | --- | --- |
| Python 3.10+ | backend, yt-dlp, gallery-dl | https://python.org |
| Node.js 20+ | builds the UI; also solves YouTube's JS challenges | https://nodejs.org |
| FFmpeg (recommended) | merges best video + audio, MP3 conversion, HLS remux | `winget install Gyan.FFmpeg` · `brew install ffmpeg` · `apt install ffmpeg` |

## Run it on this computer

```powershell
.\start.ps1
```

On macOS / Linux, run `./start.sh`. Both scripts create the virtualenv, install dependencies, build the UI, open http://127.0.0.1:8000 and start the server.

## Use it from your phone or any browser

GitHub Pages only serves static files, so the interface lives there but the downloading happens on your own server (this computer, or any machine running Landownload). The Pages site connects to it over HTTPS with an access key.

1. **Publish the interface (once).** In the repository go to *Settings → Pages → Build and deployment* and set *Source* to **GitHub Actions**. Every push to `main` then deploys the UI to `https://<your-user>.github.io/<repo>/`. If the first workflow run failed because Pages was still off, re-run it from the *Actions* tab.
2. **Expose your server.** Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) (`winget install Cloudflare.cloudflared`), then run:

   ```powershell
   .\start.ps1 -Remote
   ```

   The first run writes an access key into `.env` and allows your `github.io` site to call the server. The script prints the key and a public `https://….trycloudflare.com` address.
3. **Connect.** Open your Pages site on any device, paste the address and the access key, and you're in. Both are remembered on that device for 30 days.

The free quick-tunnel address changes every time `-Remote` starts. Tap **Server** in the header to enter the new one. For a permanent address, use a [named Cloudflare tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) or [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) (`tailscale funnel 8000`) instead. Either way, the tunnel URL also serves the full UI directly.

Without an access key the server only answers on `127.0.0.1`, so a tunnel can never expose an unprotected instance.

## Development

```bash
python -m backend    # API on :8000
npm run dev          # UI on http://127.0.0.1:5173, proxies /api to :8000
python -m pytest     # backend tests
npm test             # frontend tests
```

To try the hosted build locally: `VITE_HOSTED=1 npm run build`, then serve `dist/`.

## Keep it working

Sites change often. When downloads start failing, update the engines first:

```bash
pip install -U yt-dlp gallery-dl
```

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Meaning |
| --- | --- | --- |
| `LANDOWNLOAD_HOST` / `LANDOWNLOAD_PORT` | `127.0.0.1` / `8000` | Where the server listens. |
| `LANDOWNLOAD_TOKEN` | — | Access key. Required for any access from another device. |
| `LANDOWNLOAD_ORIGINS` | — | Websites allowed to call the API, e.g. `https://your-user.github.io`. |
| `LANDOWNLOAD_COOKIES` | — | Path to a Netscape `cookies.txt` exported from your browser, for content you can only see when signed in. |
| `LANDOWNLOAD_FFMPEG` | PATH | Folder containing `ffmpeg` if it is not on PATH. |
| `LANDOWNLOAD_DATA` | `data` | Where downloads and history live. |
| `LANDOWNLOAD_WORKERS` | `2` | Parallel downloads (1–4). A batch uses one worker and fetches its links in order. |
| `LANDOWNLOAD_RETENTION_HOURS` | `48` | Finished files are deleted after this long. |

## How it works

```
React UI (bundled, or on GitHub Pages) ──/api──▶ FastAPI (backend/app.py)
      ├─ inspect: yt-dlp (+ extra extractors in yt_dlp_plugins/) → gallery-dl → direct image
      ├─ queue + history in SQLite                               (backend/jobs.py)
      └─ one worker process per job, JSON progress on stdout      (backend/worker.py)
            single: chosen format · batch: best quality per link → ZIP
```

Security defaults: the server refuses links that resolve to private or local network addresses. Sessions are signed with a key derived from the access key. Thumbnails are proxied, so the page never contacts third-party sites directly.

## Disclaimer

This is a personal tool. Only download content you have the right to save, and respect each site's terms and the creators' rights.
