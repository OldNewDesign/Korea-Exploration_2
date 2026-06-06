#!/usr/bin/env python3
"""
Video Intelligence Pipeline
===========================
Paste video URLs in input/urls.csv -> download audio -> transcribe (Whisper)
-> translate/summarize/categorize (Claude) -> SQLite -> Excel + styled HTML guide.

Common usage:
    python process_videos.py                 # process input/urls.csv, then export
    python process_videos.py --skip-existing # don't re-process URLs already in the DB
    python process_videos.py --metadata-only # skip audio/transcription (faster, no ffmpeg)
    python process_videos.py --export-only    # rebuild Excel + guide from the DB only
    python process_videos.py --demo           # seed sample data (no network) and export

Set ANTHROPIC_API_KEY to enable AI categorization/translation. Without it, the
pipeline still runs and stores raw metadata/transcripts, flagged "needs review".
"""
import argparse
import csv
import os
import sys
from pathlib import Path


def _load_dotenv():
    """Load KEY=VALUE lines from a local .env (optional, keys stay out of git)."""
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if not os.path.exists(path):
            return
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.lower().startswith("export "):
                line = line[7:]
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


_load_dotenv()

from video_intel import config, store, export_excel, export_guide, export_map, export_share
from video_intel.platforms import detect_platform


def read_urls(path: Path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    items = []
    sniff = text.splitlines()
    has_header = sniff and "url" in sniff[0].lower()
    if has_header:
        for row in csv.DictReader(text.splitlines()):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            u = row.get("url", "")
            if u:
                items.append({"url": u, "notes": row.get("notes", "")})
    else:
        for line in sniff:
            line = line.strip()
            if line and not line.startswith("#"):
                items.append({"url": line.split(",")[0].strip(), "notes": ""})
    return items


def process_one(item, metadata_only=False):
    from video_intel import download, audio, transcribe, analyze
    url = item["url"]
    platform, cls = detect_platform(url)

    # 1) download metadata (+ audio)
    meta = download.fetch(url, download_audio=not metadata_only)

    # 2) transcribe (best effort)
    transcript_text, transcript_lang = "", ""
    if not metadata_only and meta.get("audio_file"):
        try:
            wav = audio.to_wav(meta["audio_file"], stem=Path(meta["audio_file"]).stem)
            t = transcribe.transcribe(wav)
            transcript_text, transcript_lang = t["text"], t["language"]
        except Exception as e:
            store.log_error(url, "transcribe", e)

    # 3) analyze (Claude, or heuristic fallback)
    a = analyze.analyze(meta, transcript_text, transcript_lang, url, platform, cls)

    # 4) assemble + store
    row = {
        "url": url, "platform": platform, "cls": cls, "title": meta.get("title", ""),
        "upload_date": meta.get("upload_date", ""), "duration": meta.get("duration", 0),
        "view_count": meta.get("view_count", 0), "like_count": meta.get("like_count", 0),
        "comment_count": meta.get("comment_count", 0),
        "audio_file": meta.get("audio_file", ""),
    }
    row.update(a)
    store.upsert_video(row)
    return row


def run_demo():
    samples = [
        dict(url="https://www.instagram.com/reel/EXAMPLE1/", platform="Instagram", cls="ig",
             creator="Travel Chingu", title="Seoul flame gopchang", topic="Places to Eat",
             sub_category="gopchang", summary="A famous Seoul grilled-intestine spot known for a dramatic open-flame show the owner performs once a day.",
             caption_english="Grilled beef intestines in Seoul with a huge flame show. Booked through a Korean friend.",
             caption_original="\ub9c8\ud3ec\uc9da\ubd88\uacf1\ucc3d \uc5ed\uc0bc\uc810 \uc11c\uc6b8 \uac15\ub0a8\uad6c \ub17c\ud604\ub85c 404",
             detected_language="Korean", location="Mapo Jipbul Gopchang, Yeoksam \u2014 Gangnam-gu, Seoul",
             hashtags="korea, Seoul, fire, gopchang", keywords="intestine, bbq, gangnam",
             usefulness=5, action="visit", confidence=0.9, needs_review=0),
        dict(url="https://www.tiktok.com/@example/video/EXAMPLE2", platform="TikTok", cls="tt",
             creator="seoul.coffee", title="Quiet Hongdae espresso", topic="Cafes & Desserts",
             sub_category="espresso bar", summary="Quiet minimalist espresso bar in Hongdae with single-origin pour-overs.",
             caption_english="Found the calmest espresso bar in Hongdae. Single origin only, no laptops after 2pm.",
             caption_original="", detected_language="English", location="Hongdae, Mapo-gu, Seoul",
             hashtags="seoulcafe, hongdae, coffee", keywords="espresso, pourover, quiet",
             usefulness=4, action="save", confidence=0.85, needs_review=0),
        dict(url="https://youtube.com/shorts/EXAMPLE3", platform="YouTube", cls="yt",
             creator="HikeKorea", title="Inwangsan sunrise", topic="Hikes & Nature",
             sub_category="sunrise hike", summary="Beginner-friendly sunrise route up Inwangsan with city views; ~90 min round trip.",
             caption_english="Easy Inwangsan sunrise hike, 90 min round trip, best city skyline in Seoul.",
             caption_original="", detected_language="English", location="Inwangsan, Jongno-gu, Seoul",
             hashtags="hiking, inwangsan, sunrise", keywords="trail, views, beginner",
             usefulness=4, action="visit", confidence=0.8, needs_review=0),
        dict(url="https://www.tiktok.com/@unknown/video/EXAMPLE4", platform="TikTok", cls="tt",
             creator="Unknown", title="", topic="Other",
             sub_category="", summary="(no text captured) \u2014 needs manual review.",
             caption_english="", caption_original="", detected_language="", location="",
             hashtags="", keywords="", usefulness=2, action="research", confidence=0.0, needs_review=1),
    ]
    for s in samples:
        store.upsert_video(s)
    # demo coordinates so the map populates without a network lookup
    store.update_coords("https://www.instagram.com/reel/EXAMPLE1/", 37.5006, 127.0366)
    store.update_coords("https://www.tiktok.com/@example/video/EXAMPLE2", 37.5563, 126.9236)
    store.update_coords("https://youtube.com/shorts/EXAMPLE3", 37.5879, 126.9568)
    store.log_error("https://www.instagram.com/reel/BROKEN/", "download",
                    "yt-dlp failed: login required / content unavailable")
    print(f"Seeded {len(samples)} demo videos + 1 sample error.")


def geocode_missing():
    """Fill coordinates for any stored video that has a location but no lat/lng."""
    from video_intel import geocode
    todo = [v for v in store.all_videos()
            if (v.get("location") or "").strip() and v.get("lat") in (None, "")]
    if not todo:
        return 0, 0
    prov = "Google" if config.use_google_geocode() else "OpenStreetMap"
    print(f"\nGeocoding {len(todo)} location(s) via {prov}\u2026")
    hits = 0
    for v in todo:
        res = geocode.geocode(v["location"])
        if res:
            store.update_coords(v["url"], res[0], res[1])
            hits += 1
            print(f"  \u2713 {v['location'][:60]}")
        else:
            print(f"  \u00b7 no match: {v['location'][:60]}")
    print(f"Geocoded {hits}/{len(todo)}.")
    return hits, len(todo)


def main():
    ap = argparse.ArgumentParser(description="Video Intelligence Pipeline")
    ap.add_argument("--input", default=str(config.INPUT_DIR / "urls.csv"))
    ap.add_argument("--limit", type=int, default=0, help="max URLs to process (0 = all)")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--metadata-only", action="store_true", help="skip audio + transcription")
    ap.add_argument("--export-only", action="store_true", help="only rebuild Excel + guide")
    ap.add_argument("--demo", action="store_true", help="seed sample data (no network)")
    ap.add_argument("--no-geocode", action="store_true", help="skip map geocoding")
    ap.add_argument("--share", action="store_true",
                    help="also build the publishable docs/ site (shared=1 videos, OSM map)")
    ap.add_argument("--guide-title", default=config.GUIDE_TITLE)
    args = ap.parse_args()

    config.ensure_dirs()
    store.init_db()

    if args.demo:
        run_demo()
    elif not args.export_only:
        store.clear_errors()  # Errors tab reflects only this run
        items = read_urls(Path(args.input))
        if args.limit:
            items = items[: args.limit]
        if not items:
            print(f"No URLs found in {args.input}. Add some, or use --demo.")
        ok = fail = skip = 0
        for i, item in enumerate(items, 1):
            url = item["url"]
            if args.skip_existing and store.exists(url):
                skip += 1
                print(f"[{i}/{len(items)}] skip (already stored) {url}")
                continue
            print(f"[{i}/{len(items)}] {url}")
            try:
                row = process_one(item, metadata_only=args.metadata_only)
                ok += 1
                print(f"        -> {row['topic']} | {row['creator']} | use {row['usefulness']}/5")
            except Exception as e:
                fail += 1
                store.log_error(url, "pipeline", e)
                print(f"        !! error: {e}")
        print(f"\nProcessed: {ok} ok, {fail} failed, {skip} skipped.")

    if not args.no_geocode:
        geocode_missing()

    xlsx = export_excel.build()
    guide = export_guide.build(title=args.guide_title)
    map_path, mapped, mprov = export_map.build(title=args.guide_title + " \u2014 Map")
    rows = store.all_videos()
    errs = store.all_errors()
    print("\nExports written:")
    print(f"  SQLite : {config.DB_PATH}")
    print(f"  Excel  : {xlsx}")
    print(f"  Guide  : {guide}")
    print(f"  Map    : {map_path}  ({mapped} pinned, {mprov})")
    if args.share:
        info = export_share.build(title=args.guide_title)
        print(f"  Shared : {info['dir']}  (index.html + video_map.html, {info['videos']} videos, OSM)")
    print(f"  Library: {len(rows)} videos, {sum(1 for r in rows if r.get('needs_review'))} need review, {len(errs)} errors logged.")


if __name__ == "__main__":
    sys.exit(main())
