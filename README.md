# Landownload

A private, ad-free media downloader. Paste a link from YouTube, X, Instagram, TikTok, Reddit or [a thousand other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), get a preview, and pick any quality the source offers, up to the original upload. There are no quality caps, trackers, or pop-ups.

- **Every quality**: all renditions are listed with resolution, fps, codec and size. Silent high-res streams are merged with the best audio automatically when FFmpeg is installed. There are also audio-only tracks and a 320 kbps MP3 conversion.
- **Images and galleries**: posts with several videos or photos list every item, plus an "All · ZIP" option. Photos download in their original resolution.
- **Batch → ZIP**: paste up to 50 links, one per line. Each one is fetched at its highest quality and packed into a single ZIP. Broken links don't stop the batch; they are listed in `failed-links.txt` inside the archive.
- **X / Twitter**: posts that X hides from logged-out visitors fall back to the public FxTwitter API, so they still download without cookies.
- **The tray**: live progress, speed and ETA, cancel, and download history that survives restarts. Finished files save automatically and are deleted from the server after 48 hours.
- **Paste anywhere**: press `Ctrl+V` anywhere on the page to fetch a link. Pasting several links at once opens the batch composer.
- **Use it from anywhere**: the interface is published on GitHub Pages and talks to the app running on your PC. When the PC's app is stopped, the site says so.

## Run it (Docker, one click)

Needs [Docker Desktop](https://www.docker.com/products/docker-desktop/) (`winget install -e --id Docker.DockerDesktop`).

- Double-click **`Start Landownload.cmd`** to turn it on, and **`Stop Landownload.cmd`** to turn it off.
- For desktop icons, run `powershell -ExecutionPolicy Bypass -File docker\landownload.ps1 shortcuts` once.

Starting brings up two containers:

- **app**: Landownload with FFmpeg and Node included. It is always available on this PC at http://127.0.0.1:8000.
- **tailscale**: a [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) that gives the PC a permanent public address, `https://landownload.<your-tailnet>.ts.net`.

The first start builds the image (a few minutes) and opens a Tailscale sign-in page once. A free account works, and you can sign in with GitHub. In the [Tailscale admin console](https://login.tailscale.com/admin/dns), enable **HTTPS Certificates**. The launcher prints the public address when everything is up.

Downloads and history live in the `downloads` Docker volume. Each browser only sees its own downloads.

## The website (GitHub Pages)

1. In the repository, go to *Settings → Pages* and set *Source* to **GitHub Actions**. Every push to `main` deploys the UI to `https://<your-user>.github.io/<repo>/`.
2. Put the public address printed by the launcher into `server-url.txt` and push. The site then connects to your PC by itself.

While the app is running, the site works from any phone or computer. While it's stopped, visitors see **"Server is off"**, and the page reconnects automatically once you start it again.

The app has no access key in this setup, so anyone who has the site's link can use it while it's on. Files are removed after 48 hours, and the queue is capped at 12 jobs.

## Run it without Docker

Requires Python 3.10+, Node.js 20+, and FFmpeg (recommended).

```powershell
.\start.ps1
```

On macOS / Linux, run `./start.sh`. These scripts create a virtualenv, build the UI and serve it at http://127.0.0.1:8000. Without Docker, the server only answers on this PC unless you set `LANDOWNLOAD_TOKEN` or `LANDOWNLOAD_OPEN=1`.

## Development

```bash
python -m backend    # API on :8000
npm run dev          # UI on http://127.0.0.1:5173, proxies /api to :8000
python -m pytest     # backend tests
npm test             # frontend tests
```

To try the hosted build locally: `VITE_HOSTED=1 VITE_SERVER_URL=http://127.0.0.1:8000 npm run build`, then serve `dist/`.

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
| `LANDOWNLOAD_OPEN` | `1` in Docker | Allow access from other devices without a key. |
| `LANDOWNLOAD_TOKEN` | — | Optional access key; when set, the UI asks for it. |
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

Security defaults: the server refuses links that resolve to private or local network addresses, only accepts browser calls from its own page and `LANDOWNLOAD_ORIGINS`, and each browser can only see and cancel its own downloads. Thumbnails are proxied, so the page never contacts third-party sites directly.

## Disclaimer

This is a personal tool. Only download content you have the right to save, and respect each site's terms and the creators' rights.
