<p align="center">
  <img src="public/favicon.svg" width="72" alt="" />
</p>

<h1 align="center">Landownload</h1>

<p align="center">
  <b>Paste a link, keep the file.</b><br />
  A private media downloader with no ads, no quality caps, and no nonsense.<br />
  <a href="https://elmariones.github.io/Landownload/"><b>Open Landownload →</b></a>
</p>

---

Landownload fetches videos, audio and images from YouTube, X, Instagram, TikTok, Reddit, Vimeo and [over a thousand other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md). The website runs on GitHub Pages, and the downloading happens on your own PC. Turn the PC's app on and the site works from any phone or computer. Turn it off and the site tells visitors the server is off.

## Features

| | |
| --- | --- |
| **Every quality** | Lists every rendition the source offers, up to the original upload, with resolution, fps, codec and size. High-res streams without sound are merged with the best audio automatically. |
| **Audio** | Audio-only tracks at every bitrate, plus a 320 kbps MP3 conversion. |
| **Images & galleries** | Photos come in original resolution. Posts with several videos or photos list each item, plus an **All · ZIP** option. |
| **Batch → ZIP** | Paste up to 50 links, one per line, and get each one at its best quality in a single ZIP. Links that fail don't stop the batch; they're listed in `failed-links.txt` inside the archive. |
| **Live tray** | Shows progress, speed and time left, with cancel. Finished files save automatically, and each browser only sees its own downloads. |
| **Paste anywhere** | Press <kbd>Ctrl</kbd>+<kbd>V</kbd> anywhere on the page to fetch a link. Pasting several links at once opens the batch composer. |
| **X / Twitter** | Posts that X hides from logged-out visitors are fetched through the public FxTwitter API, so no cookies are needed. |
| **Private** | No ads or tracking. Thumbnails are proxied through your server, and files are deleted after 48 hours. |

## Everyday use

| To | Do this |
| --- | --- |
| Turn it **on** | Double-click **Start Landownload** on the Desktop. |
| Turn it **off** | Double-click **Stop Landownload**. |
| Use it from anywhere | Open **https://elmariones.github.io/Landownload/** |
| Use it on this PC | Open http://127.0.0.1:8000 |

While it's off, the website shows *"Server is off — the server has been turned off by the admin"*. It reconnects by itself as soon as you start it again.

> The PC must be on with Landownload started for the website to work. There's no access key, so anyone with the link can use it while it's on. The queue is capped at 12 jobs and files are deleted after 48 hours.

## First-time setup

You only do this once per PC.

1. **Install Docker Desktop**, then open it once and finish its setup.
   ```powershell
   winget install -e --id Docker.DockerDesktop
   ```
2. **Create the desktop shortcuts** (optional; `Start Landownload.cmd` and `Stop Landownload.cmd` in this folder do the same):
   ```powershell
   powershell -ExecutionPolicy Bypass -File docker\landownload.ps1 shortcuts
   ```
3. **Set up Tailscale.** It gives your PC a permanent public HTTPS address for free.
   - Create a free account at [tailscale.com](https://tailscale.com); you can sign in with GitHub.
   - In the [admin console → DNS](https://login.tailscale.com/admin/dns), enable **HTTPS Certificates**.
   - Run **Start Landownload**. The first start builds the app, which takes a few minutes. It then opens the [auth key page](https://login.tailscale.com/admin/settings/keys) and a `.env` file. Generate a key, paste it after `TS_AUTHKEY=`, save, and run **Start** again. The key is used once; later starts reuse the saved login.
   - If Funnel (the feature that publishes the address) is off for your account, the launcher opens a page to enable it. Click **Enable** and start again.

   The launcher prints the public address when everything is up, for example `https://landownload.tailxxxx.ts.net`.
4. **Publish the website.**
   - In the repository, go to *Settings → Pages* and set *Source* to **GitHub Actions**.
   - Put the public address into `server-url.txt` and push. Every push to `main` rebuilds the site with that address built in.

## How it works

```
 Phone / PC browser
        │
        ▼
 GitHub Pages ── the website (React), with your server's address built in
        │  HTTPS API calls
        ▼
 Tailscale Funnel ── permanent public address  ┐
        │                                       │ Docker on your PC
        ▼                                       │
 Landownload app ── FastAPI + yt-dlp + gallery-dl + FFmpeg
```

- **Previews:** yt-dlp (plus the extra extractors in `yt_dlp_plugins/`) reads every available format. gallery-dl handles image posts, and plain image links are fetched directly.
- **Downloads:** each one runs in its own worker process that reports progress. Single downloads use the format you picked; batches take the best of each link and zip them.
- **History:** kept in SQLite inside the `downloads` Docker volume.
- **Safety:** links that point to private or local network addresses are refused. The API only accepts browser calls from its own page and from the origins in `LANDOWNLOAD_ORIGINS`. Each browser can only see and cancel its own downloads.

## Configuration

The Docker setup needs nothing beyond the one-time `TS_AUTHKEY`. Optional settings go in `.env` next to `docker-compose.yml` and apply on the next **Start**:

| Variable | Default | Meaning |
| --- | --- | --- |
| `TS_AUTHKEY` | — | One-time Tailscale auth key for the first start. |
| `LANDOWNLOAD_ORIGINS` | `https://elmariones.github.io` | Websites allowed to call the API. |
| `LANDOWNLOAD_WORKERS` | `2` | Parallel downloads (1–4). A batch uses one worker. |
| `LANDOWNLOAD_RETENTION_HOURS` | `48` | Finished files are deleted after this long. |
| `LANDOWNLOAD_TOKEN` | — | Optional access key. When set, the website asks for it. |

Running without Docker also supports `LANDOWNLOAD_COOKIES` (see `.env.example`), a path to a `cookies.txt` file exported from your browser, for content you can only see when signed in.

## Keeping it working

Sites change often. When downloads start failing, rebuild the app to pick up the newest yt-dlp and gallery-dl:

```powershell
docker compose build --pull --no-cache app
```

Then run **Start Landownload** again.

## Development

Without Docker (Python 3.10+, Node.js 20+, FFmpeg recommended):

```powershell
.\start.ps1                # builds the UI and serves everything on http://127.0.0.1:8000
```

With hot reload, in two terminals:

```bash
python -m backend          # API on :8000
npm run dev                # UI on http://127.0.0.1:5173, proxies /api to :8000
```

Tests:

```bash
python -m pytest           # backend
npm test                   # frontend
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The website says **Server is off**, but it's on | Wait about 20 seconds after starting. If it persists, run **Stop** and then **Start** again. |
| The launcher says the public address isn't answering | Check that HTTPS Certificates is enabled in the Tailscale DNS settings and that Funnel is enabled. The launcher opens the Funnel page for you. |
| "Tailscale rejected the auth key" | Generate a new key, replace it in `.env`, and start again. |
| A site stopped working | Rebuild to update the engines (see [Keeping it working](#keeping-it-working)). |

## Disclaimer

Landownload is a personal tool. Only download content you have the right to save, and respect each site's terms and its creators' rights.
