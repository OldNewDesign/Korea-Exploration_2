# Video Intelligence Pipeline

Paste video URLs → download audio → transcribe with Whisper → translate /
summarize / categorize with Claude → store in **SQLite** → export a **multi-tab
Excel workbook** and a **styled HTML guide** (identical look to the Korea &
Seoul web app).

```
URLs (input/urls.csv)
        │
        ▼
  yt-dlp  ──►  FFmpeg  ──►  Whisper  ──►  Claude
 (metadata    (16k mono    (transcript)  (translate +
  + audio)      wav)                      categorize)
        │
        ▼
   SQLite  ──►  Excel (.xlsx)  +  Guide (.html)  +  Map (.html)
 (source of truth)
```

## Quick start (Windows / PowerShell)

```powershell
# from the project folder (the one containing app.py)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
winget install Gyan.FFmpeg        # for transcription; open a NEW window after
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # optional but recommended
python -m streamlit run app.py    # web UI  (or use the CLI below)
```

Try it with zero setup (no keys, no network): `python process_videos.py --demo`,
then open `output/video_guide.html` and `output/video_map.html`.

## Create the GitHub repository

```powershell
git init
git add .
git status          # confirm .env and output/ are NOT listed
git commit -m "Initial commit: video intelligence pipeline"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

`.gitignore` already excludes your secrets (`.env`) and private library
(`output/`, `downloads/`, `audio/`, `transcripts/`), while keeping `docs/`
(the publishable, key-free site) committed. **Never commit an API key — if one
ever lands in history, rotate it.**

## GPU (NVIDIA, e.g. RTX 4090)

Whisper uses the GPU automatically **if** PyTorch is the CUDA build. Check:

```powershell
python -c "import torch; print(torch.cuda.is_available())"
```

If `False`, install the CUDA build (huge speedup for transcription):

```powershell
pip uninstall -y torch
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

This project then runs Whisper on `cuda` with fp16 automatically.


## Install

```bash
cd video-intel-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# FFmpeg is a system tool:
#   macOS: brew install ffmpeg   |   Ubuntu: sudo apt install ffmpeg   |   Windows: choco install ffmpeg
```

Set your key (optional but recommended):

```bash
cp .env.example .env   # edit it, then:
source .env
```

## Try it without any setup

```bash
python process_videos.py --demo
open output/video_guide.html       # and output/video_library.xlsx
```

`--demo` seeds sample data (no network, no API) so you can see the outputs.

## Web UI (Streamlit)

Prefer pasting links into a page over editing a CSV? Run the front-end:

```bash
pip install streamlit
python -m streamlit run app.py
```

It opens in your browser. Paste links, click **Process**, watch the live
progress log, then preview and download the guide, map, and Excel right there.
Settings (API keys, Whisper model, metadata-only, categories, guide title) live
in the sidebar. It shares the same `output/video_intel.db`, so the CLI and the
UI work on the same library interchangeably.

## Command line

1. Put links in `input/urls.csv` (a `url` column, or just one URL per line).
2. Run:

```bash
python process_videos.py                 # full pipeline, then export
python process_videos.py --skip-existing # don't re-process stored URLs
python process_videos.py --metadata-only # skip audio + Whisper (no ffmpeg needed)
python process_videos.py --export-only   # rebuild Excel + guide from the DB
python process_videos.py --guide-title "Korea & Seoul"
```

Outputs land in `output/`:
- `video_intel.db` — SQLite, the real store
- `video_library.xlsx` — All Videos + a tab per category + Needs Review + Errors
- `video_guide.html` — the shareable, searchable guide
- `video_map.html` — interactive map of every location that geocoded (markers by platform, popups link to the video + Google Maps)

## The map

Any video whose `location` resolves to a real place is pinned on `video_map.html`,
and the guide header has a **View map** button that links straight to it.

**Renderer + geocoder:** if `GOOGLE_MAPS_API_KEY` is set, the map renders with
the **Google Maps JavaScript API** and geocoding uses **Google** (best for messy
or Korean addresses). Enable both *Maps JavaScript API* and *Geocoding API* for
that key in the Google Cloud console. Without a key it falls back to **Leaflet +
OpenStreetMap** (free, no key) and Nominatim geocoding at ~1 lookup/sec.

Every result is cached in the DB, so places are never looked up twice. Skip
geocoding with `--no-geocode`. Re-pin an existing library any time with:

```bash
python process_videos.py --export-only   # geocodes anything missing, rebuilds all exports
```

> The Maps JS key is embedded in the local `video_map.html`. That's fine for
> personal use; if you share the file, restrict the key (API + quota limits, and
> an HTTP-referrer restriction) in the Google Cloud console first.

## How categorization works

Each video is bucketed into one category from `video_intel/config.py` →
`CATEGORIES` (defaults match the Korea & Seoul guide; edit freely). Anything the
model is unsure about, or that scores low, lands in **Needs Review** so nothing
is silently mislabeled.


## Publish a curated subset (GitHub Pages)

Share a hand-picked set of spots as a public link, updated whenever you like.

1. In the **web UI -> Share (publish)** tab, tick the videos to include and click **Save selection**.
2. Click **Build shareable site (OpenStreetMap)**. This writes a `docs/` folder:
   `docs/index.html` (guide) + `docs/video_map.html` (map) + `.nojekyll`.
   The shared map *always* uses OpenStreetMap, so no API key is ever published.
3. Commit and push `docs/`, then enable Pages:
   - `git add docs && git commit -m "publish guide" && git push`
   - GitHub -> **Settings -> Pages -> Deploy from a branch -> main -> /docs**.
   - Your link: `https://<you>.github.io/<repo>/`
4. Add more spots later, rebuild, push again. Same link, fresh content.

CLI equivalent: `python process_videos.py --share` (builds `docs/` from videos
you've marked shared). Or grab `docs.zip` from the Share tab to drag onto Netlify.

> Keep `output/` in your `.gitignore` (it holds your full private library), but do
> **commit** `docs/` — that folder is the curated, key-free version meant to be public.


## Notes & etiquette

- Works on **public or your own** content. Don't bypass logins, paywalls, or
  privacy settings — use account cookies/authorization only for content you own.
- Links will sometimes fail (private, expired, region-locked). Those are caught
  and written to the **Errors** tab; the run continues.
- No `ANTHROPIC_API_KEY`? The pipeline still downloads + transcribes and stores
  everything, flagged for review — add the key later and re-run to enrich.

## Layout

```
process_videos.py            # CLI orchestrator
app.py                       # Streamlit web UI
requirements.txt  .env.example
input/urls.csv               # your links
video_intel/
  config.py                  # paths, model, categories
  platforms.py               # URL -> platform
  download.py                # yt-dlp
  audio.py                   # ffmpeg -> 16k mono wav
  transcribe.py              # local Whisper
  analyze.py                 # Claude (translate/summarize/categorize) + fallback
  store.py                   # SQLite schema + upsert/query + geocache
  geocode.py                 # OpenStreetMap geocoding (cached, rate-limited)
  export_excel.py            # multi-tab workbook
  export_guide.py            # HTML guide (matches the web app)
  export_map.py              # interactive Leaflet/Google map
  export_share.py            # publishable docs/ site (curated subset)
  guide_assets.py            # the exact guide CSS/JS
downloads/  audio/  transcripts/  output/   # created on first run
```
