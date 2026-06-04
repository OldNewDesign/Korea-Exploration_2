"""
Streamlit front-end for the Video Intelligence Pipeline.

Run it from the project folder:
    pip install streamlit
    python -m streamlit run app.py

Everything the CLI does, in a browser: paste links, watch progress, then preview
and download the guide, map, and Excel. Uses the same backend modules, so the
SQLite library is shared with `process_videos.py`.
"""
import os
import io
import zipfile
import streamlit as st

from video_intel import config, store, transcribe, export_excel, export_guide, export_map, export_share
import process_videos as pv

st.set_page_config(page_title="Video Intelligence", page_icon="🎬", layout="wide")
config.ensure_dirs()
store.init_db()


# ----------------------------- helpers ------------------------------------
def parse_links(text):
    items, seen = [], set()
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # support "url | note"
        url = line.split("|")[0].strip()
        for tok in line.split():
            if tok.startswith("http"):
                url = tok.strip()
                break
        if url.startswith("http") and url not in seen:
            seen.add(url)
            items.append({"url": url, "notes": ""})
    return items


def file_dl(path, label, mime):
    if os.path.exists(path):
        with open(path, "rb") as f:
            st.download_button(label, f.read(), file_name=os.path.basename(path),
                               mime=mime, use_container_width=True)
    else:
        st.button(label + " (not built yet)", disabled=True, use_container_width=True)


def rebuild_exports(title, do_geocode):
    geo_hits = geo_total = 0
    if do_geocode:
        geo_hits, geo_total = pv.geocode_missing()
    export_excel.build()
    export_guide.build(title=title)
    _, mapped, mprov = export_map.build(title=title + " \u2014 Map")
    return mapped, mprov, geo_hits, geo_total


# ----------------------------- sidebar ------------------------------------
with st.sidebar:
    st.header("Settings")

    key = st.text_input("Anthropic API key", type="password", value=config.ANTHROPIC_API_KEY,
                        help="Enables translation/categorization. Without it, videos are stored raw and flagged for review.")
    model = st.text_input("Claude model", value=config.ANALYZE_MODEL)
    gkey = st.text_input("Google Maps API key", type="password", value=config.GOOGLE_MAPS_API_KEY,
                        help="If set, the map renders with Google Maps and geocoding uses Google. Otherwise OpenStreetMap.")

    st.divider()
    meta_only = st.checkbox("Metadata only (skip audio + Whisper)", value=True,
                            help="Fast, no FFmpeg needed. Uncheck to transcribe speech with Whisper.")
    whisper_model = st.selectbox("Whisper model", ["tiny", "base", "small", "medium", "large-v3", "turbo"],
                                 index=2, disabled=meta_only)
    do_geocode = st.checkbox("Geocode locations for the map", value=True)
    map_renderer = st.radio(
        "Map renderer", ["OpenStreetMap (recommended)", "Google"], index=0,
        help="OpenStreetMap always renders inside this app. Google needs the Maps "
             "JavaScript API enabled and usually won't preview in-app (the downloadable "
             "file may still work). Geocoding still uses Google if a key is set.")
    skip_existing = st.checkbox("Skip links already in the library", value=True)

    st.divider()
    title = st.text_input("Guide title", value=config.GUIDE_TITLE)
    cats_text = st.text_area("Categories (one per line)", value="\n".join(config.CATEGORIES), height=180)

# apply settings to the shared config (read at call time by the backend)
config.ANTHROPIC_API_KEY = key.strip()
config.ANALYZE_MODEL = model.strip() or config.ANALYZE_MODEL
config.GOOGLE_MAPS_API_KEY = gkey.strip()
config.WHISPER_MODEL = whisper_model
# Geocoding can use Google (quality) while the map renders with OSM (reliable in-app).
config.MAP_PROVIDER = "google" if map_renderer.startswith("Google") else "osm"
cats = [c.strip() for c in cats_text.splitlines() if c.strip()]
if cats:
    config.CATEGORIES = cats
# reload Whisper only if the choice changed
if st.session_state.get("_whisper") != whisper_model:
    transcribe._MODEL = None
    st.session_state["_whisper"] = whisper_model


# ----------------------------- header -------------------------------------
st.title("🎬 Video Intelligence")
st.caption("Paste links → transcribe → translate → categorize → guide, map & spreadsheet.")

lib = store.all_videos()
errs = store.all_errors()
geo = sum(1 for v in lib if v.get("lat") not in (None, ""))
shared_n = sum(1 for v in lib if v.get("shared"))
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Videos", len(lib))
c2.metric("Mapped", geo)
c3.metric("Shared", shared_n)
c4.metric("Need review", sum(1 for v in lib if v.get("needs_review")))
c5.metric("Errors", len(errs))

tab_proc, tab_lib, tab_map, tab_share, tab_err = st.tabs(
    ["Paste & Process", "Library", "Map & Guide", "Share (publish)", "Errors"])


# ----------------------------- process tab --------------------------------
with tab_proc:
    if not config.ANTHROPIC_API_KEY:
        st.info("No Anthropic key set — videos will be stored with raw captions and flagged for review. "
                "Add a key in the sidebar for translation + smart categories.")
    if not meta_only and config.use_google_map():
        pass
    text = st.text_area("Paste video URLs (one per line; `url | note` is fine)", height=180,
                        placeholder="https://www.instagram.com/reel/...\nhttps://www.tiktok.com/@user/video/...\nhttps://youtube.com/shorts/...")
    colA, colB = st.columns([1, 1])
    go = colA.button("⚡ Process links", type="primary", use_container_width=True)
    rebuild = colB.button("🔁 Rebuild exports from library", use_container_width=True,
                          help="Re-geocode anything missing and regenerate the guide, map, and Excel.")

    if go:
        items = parse_links(text)
        if not items:
            st.warning("No URLs found.")
        else:
            prog = st.progress(0.0, text="Starting…")
            logbox = st.empty()
            log = []
            ok = fail = skip = 0
            for i, item in enumerate(items, 1):
                url = item["url"]
                if skip_existing and store.exists(url):
                    skip += 1
                    log.append(f"⏭️  skip (already stored) — {url}")
                else:
                    try:
                        row = pv.process_one(item, metadata_only=meta_only)
                        ok += 1
                        log.append(f"✓ {row['topic']} · {row['creator']} · use {row['usefulness']}/5 — {url}")
                    except Exception as e:
                        fail += 1
                        store.log_error(url, "pipeline", e)
                        log.append(f"❌ {e}  — {url}")
                prog.progress(i / len(items), text=f"{i}/{len(items)} processed")
                logbox.code("\n".join(log[-15:]))

            with st.spinner("Geocoding + building guide, map, and Excel…"):
                mapped, mprov, gh, gt = rebuild_exports(title, do_geocode)
            st.success(f"Done — {ok} processed, {skip} skipped, {fail} failed. "
                       f"{mapped} pinned on the map ({mprov}).")
            if do_geocode:
                if gt and gh == 0:
                    st.error(f"Geocoded 0 of {gt} locations. If you're using a Google key, make sure the "
                             "**Geocoding API** is enabled for it (not just Maps JavaScript). "
                             "Use **Test geocoding** in the Map & Guide tab to see the exact error.")
                elif gt:
                    st.info(f"Geocoded {gh} of {gt} new location(s).")
            st.rerun()

    if rebuild:
        with st.spinner("Rebuilding…"):
            mapped, mprov, gh, gt = rebuild_exports(title, do_geocode)
        st.success(f"Exports rebuilt — {mapped} pinned ({mprov}). Geocoded {gh}/{gt} new.")
        st.rerun()


# ----------------------------- library tab --------------------------------
with tab_lib:
    if not lib:
        st.info("No videos yet. Paste some links in the first tab.")
    else:
        view = [{
            "Platform": v.get("platform"), "Creator": v.get("creator"),
            "Category": v.get("topic"), "Sub": v.get("sub_category"),
            "Location": v.get("location"), "Use": v.get("usefulness"),
            "Action": v.get("action"), "Review": "⚠️" if v.get("needs_review") else "",
            "Summary": v.get("summary"), "URL": v.get("url"),
        } for v in lib]
        plats = sorted({v.get("platform") for v in lib if v.get("platform")})
        topics = sorted({v.get("topic") for v in lib if v.get("topic")})
        f1, f2, f3 = st.columns(3)
        fp = f1.multiselect("Platform", plats)
        ft = f2.multiselect("Category", topics)
        fq = f3.text_input("Search")
        rows = view
        if fp:
            rows = [r for r in rows if r["Platform"] in fp]
        if ft:
            rows = [r for r in rows if r["Category"] in ft]
        if fq:
            ql = fq.lower()
            rows = [r for r in rows if ql in " ".join(str(x) for x in r.values()).lower()]
        st.dataframe(rows, use_container_width=True, hide_index=True,
                     column_config={"URL": st.column_config.LinkColumn("URL")})


# ----------------------------- map & guide tab ----------------------------
with tab_map:
    d1, d2, d3 = st.columns(3)
    with d1:
        file_dl(str(config.GUIDE_PATH), "⬇ Guide (HTML)", "text/html")
    with d2:
        file_dl(str(config.MAP_PATH), "⬇ Map (HTML)", "text/html")
    with d3:
        file_dl(str(config.EXCEL_PATH), "⬇ Excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    sub_guide, sub_map = st.tabs(["Guide preview", "Map preview"])
    with sub_guide:
        if os.path.exists(config.GUIDE_PATH):
            st.components.v1.html(open(config.GUIDE_PATH, encoding="utf-8").read(),
                                  height=820, scrolling=True)
        else:
            st.info("Build the guide first (process links or rebuild exports).")
    with sub_map:
        if os.path.exists(config.MAP_PATH):
            st.components.v1.html(open(config.MAP_PATH, encoding="utf-8").read(),
                                  height=820, scrolling=True)
        else:
            st.info("Build the map first.")

    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        if st.button("🔄 Re-geocode failures (clear cache & retry)", use_container_width=True):
            with st.spinner("Re-geocoding…"):
                store.clear_geocache(misses_only=True)
                gh, gt = pv.geocode_missing()
                export_guide.build(title=title)
                export_map.build(title=title + " \u2014 Map")
            st.success(f"Re-geocoded {gh}/{gt}. Switch to Map preview to see pins.")
            st.rerun()
    with g2:
        with st.expander("🧪 Test geocoding (diagnose failures)"):
            sample = st.text_input("Address / place to test", value="Hongdae, Mapo-gu, Seoul")
            if st.button("Run test"):
                from video_intel import geocode as _gc
                st.json(_gc.probe(sample))


# ----------------------------- share tab ----------------------------------
with tab_share:
    st.subheader("Publish a curated subset")
    st.caption("Tick the videos to make public, Save, then build the site. The "
               "shared map always uses OpenStreetMap, so no API key is ever published.")
    if not lib:
        st.info("No videos yet.")
    else:
        editor_rows = [{
            "Share": bool(v.get("shared")),
            "Creator": v.get("creator"), "Category": v.get("topic"),
            "Location": v.get("location") or "", "URL": v.get("url"),
        } for v in lib]
        bcol1, bcol2, bcol3 = st.columns(3)
        if bcol1.button("Select all"):
            for v in lib:
                store.set_shared(v["url"], True)
            st.rerun()
        if bcol2.button("Select none"):
            for v in lib:
                store.set_shared(v["url"], False)
            st.rerun()
        edited = st.data_editor(
            editor_rows, hide_index=True, use_container_width=True, key="share_editor",
            disabled=["Creator", "Category", "Location", "URL"],
            column_config={"URL": st.column_config.LinkColumn("URL"),
                           "Share": st.column_config.CheckboxColumn("Share", default=False)},
        )
        if st.button("💾 Save selection"):
            for r in edited:
                store.set_shared(r["URL"], r.get("Share"))
            st.rerun()

        st.divider()
        pub_title = st.text_input("Public guide title", value=config.GUIDE_TITLE)
        if st.button("🌐 Build shareable site (OpenStreetMap)", type="primary"):
            if shared_n == 0:
                st.warning("No videos marked Share yet — tick some above and Save first.")
            else:
                with st.spinner("Building docs/ …"):
                    info = export_share.build(title=pub_title)
                st.success(f"Built {info['videos']} videos ({info['mapped']} pinned) into "
                           f"`{info['dir']}` using {info['provider']}.")

        # offer a zip of docs/ for drag-and-drop hosting (Netlify, etc.)
        if os.path.isdir(config.SHARE_DIR) and os.path.exists(os.path.join(config.SHARE_DIR, "index.html")):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for root, _, files in os.walk(config.SHARE_DIR):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        z.write(fp, os.path.relpath(fp, config.SHARE_DIR))
            st.download_button("⬇ Download docs.zip (for Netlify/Drive)", buf.getvalue(),
                               file_name="docs.zip", mime="application/zip")
            with st.expander("Publish on GitHub Pages (durable link)"):
                st.markdown(
                    "1. Commit the new **`docs/`** folder: `git add docs && git commit -m \"publish guide\" && git push`\n"
                    "2. On GitHub: **Settings → Pages → Source = Deploy from a branch**, "
                    "branch **main**, folder **/docs**, Save.\n"
                    "3. Your link appears in a minute: `https://<you>.github.io/<repo>/`\n\n"
                    "Re-run this build and push again whenever you add spots — the link stays the same.")
            with st.expander("Preview the shared guide"):
                st.components.v1.html(
                    open(os.path.join(config.SHARE_DIR, "index.html"), encoding="utf-8").read(),
                    height=720, scrolling=True)


# ----------------------------- errors tab ---------------------------------
with tab_err:
    if not errs:
        st.success("No errors logged.")
    else:
        st.caption("Errors from the latest run (links that failed to download/process).")
        st.dataframe(
            [{"URL": e.get("url"), "Stage": e.get("stage"), "Message": e.get("message"), "When": e.get("ts")}
             for e in errs],
            use_container_width=True, hide_index=True,
            column_config={"URL": st.column_config.LinkColumn("URL")},
        )
