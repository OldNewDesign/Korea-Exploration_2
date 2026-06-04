"""Render the SQLite data as a standalone HTML guide — identical in look and
behavior to the web app's export (same CSS, same interaction JS)."""
import html
from datetime import date
from urllib.parse import quote
from . import config, store
from .platforms import watch_label
from .guide_assets import GUIDE_CSS, GUIDE_JS, FONTS


def esc(s):
    return html.escape("" if s is None else str(s), quote=True)


def _split(s):
    if not s:
        return []
    return [t.strip().lstrip("#") for t in str(s).replace(",", " ").split() if t.strip()]


def _map_href(loc):
    return "https://www.google.com/maps/search/?api=1&query=" + quote(loc)


def _pin(sz):
    return (f'<svg width="{sz}" height="{sz}" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2.2"><path d="M12 21s-7-6.3-7-11a7 7 0 0 1 '
            '14 0c0 4.7-7 11-7 11z"/><circle cx="12" cy="10" r="2.4"/></svg>')


def build_card(v):
    cls = v.get("cls") or "other"
    platform = v.get("platform") or "Other"
    topic = v.get("topic") or "Other"
    tags = _split(v.get("hashtags"))
    cap_o = (v.get("caption_original") or "").strip()
    cap_e = (v.get("caption_english") or "").strip()
    has_orig = bool(cap_o) and cap_o != cap_e
    has_tags = bool(tags)
    has_extra = has_orig or has_tags
    loc = (v.get("location") or "").strip()
    url = (v.get("url") or "").strip()

    h = [f'<article class="card {cls}" data-plat="{esc(platform)}" data-topic="{esc(topic)}"><div class="cbody">']
    h.append(f'<div class="toprow"><div class="uploader"><span class="at">@</span>'
             f'{esc(v.get("creator") or "Unknown")}</div><span class="topic-tag">{esc(topic)}</span></div>')
    h.append(f'<div class="platrow"><span class="plat {cls}">{esc(platform)}</span>')
    if v.get("sub_category"):
        h.append(f'<span class="lang-tag">{esc(v["sub_category"])}</span>')
    h.append(f'<span class="badge-use">\u2605 {int(v.get("usefulness") or 3)}/5</span>')
    if v.get("action"):
        h.append(f'<span class="badge-act">{esc(v["action"])}</span>')
    h.append("</div>")
    if loc:
        h.append(f'<a class="loc" href="{esc(_map_href(loc))}" target="_blank" rel="noopener">'
                 f'{_pin(14)}<span>{esc(loc)}</span></a>')
    h.append(f'<div class="desc{" clamp" if has_extra else ""}">'
             f'{esc(v.get("summary") or "(no description)")}</div>')
    if has_extra:
        h.append('<button class="more">Show more \u2193</button><div class="extra">')
        if has_orig:
            lang = v.get("detected_language") or ""
            mid = (" \u00b7 " + esc(lang)) if lang else ""
            h.append("<h4>Original" + mid + "</h4>"
                     f'<div class="blk orig">{esc(cap_o)}</div>')
        if has_tags:
            chips = "".join(f'<button class="tag" data-tag="{esc(t)}">#{esc(t)}</button>' for t in tags)
            h.append(f'<div class="tags">{chips}</div>')
        h.append("</div>")
    h.append('</div><div class="cardfoot">')
    if url:
        h.append(f'<a class="watch" href="{esc(url)}" target="_blank" rel="noopener">{esc(watch_label(platform))}</a>')
    if loc:
        h.append(f'<a class="maplink" href="{esc(_map_href(loc))}" target="_blank" rel="noopener">{_pin(15)}Map</a>')
    h.append("</div></article>")
    return "".join(h)


def build_controls_and_content(rows):
    by_topic = {}
    for v in rows:
        by_topic.setdefault(v.get("topic") or "Other", []).append(v)
    order = [c for c in config.CATEGORIES if c in by_topic]
    order += [c for c in by_topic if c not in order]
    plats = []
    for v in rows:
        p = v.get("platform") or "Other"
        if p not in plats:
            plats.append(p)

    chips = [f'<button class="chip active" data-topic="all">All<span class="n">{len(rows)}</span></button>']
    for c in order:
        chips.append(f'<button class="chip" data-topic="{esc(c)}">{esc(c)}<span class="n">{len(by_topic[c])}</span></button>')
    seg = ['<button data-plat="all" class="active">All</button>']
    for p in plats:
        seg.append(f'<button data-plat="{esc(p)}">{esc(p)}</button>')

    sections = []
    for c in order:
        sections.append(f'<section class="section" data-topic="{esc(c)}"><div class="section-head">'
                        f'<h2>{esc(c)}</h2><span class="cnt">{len(by_topic[c])}</span></div><div class="grid">')
        sections.extend(build_card(v) for v in by_topic[c])
        sections.append("</div></section>")

    return (
        '<div class="controls"><div class="wrap"><div class="controlrow"><div class="searchbar">'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">'
        '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.6" y2="16.6"/></svg>'
        '<input id="gSearch" type="search" inputmode="search" placeholder="Search places, food, hashtags\u2026" autocomplete="off">'
        '<button class="clear-btn" id="gClear" aria-label="clear">&times;</button></div>'
        f'<div class="segment" id="gSeg">{"".join(seg)}</div></div>'
        f'<div class="chips" id="gChips">{"".join(chips)}</div>'
        '<div class="resultline" id="gResult"></div></div></div>'
        f'<main id="content"><div class="wrap">{"".join(sections)}'
        '<div class="empty" id="gEmpty">No videos match \u2014 try clearing filters.</div>'
        '</div></main>'
    )


def build_guide(rows, title=None, map_href="video_map.html"):
    title = title or config.GUIDE_TITLE
    ig = sum(1 for v in rows if v.get("platform") == "Instagram")
    tt = sum(1 for v in rows if v.get("platform") == "TikTok")
    stat = f'<b>{len(rows)}</b> videos'
    if ig:
        stat += f' \u00b7 <span class="ig"><b>{ig}</b> Instagram</span>'
    if tt:
        stat += (' + ' if ig else ' \u00b7 ') + f'<span class="tt"><b>{tt}</b> TikTok</span>'
    body = build_controls_and_content(rows)
    map_link = (
        '<p style="margin:14px 0 0"><a href="' + esc(map_href) + '" '
        'style="display:inline-flex;align-items:center;gap:7px;background:#c8472f;color:#fff;'
        'font-family:inherit;font-weight:700;font-size:.9rem;text-decoration:none;'
        'padding:9px 18px;border-radius:999px">' + _pin(15) + 'View map \u2192</a></p>'
    )
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=5">'
        f'<title>{esc(title)}</title><meta name="theme-color" content="#c8472f">'
        f'{FONTS}<style>{GUIDE_CSS}</style></head><body>'
        '<header class="hero"><div class="wrap"><div class="kicker">Saved Video Guide</div>'
        f'<h1 class="title">{esc(title)}</h1>'
        '<p class="subtitle">Categorized by topic \u00b7 built with the video pipeline</p>'
        f'<p class="statline">{stat}</p>{map_link}</div></header>'
        f'<div id="resultsRegion">{body}</div>'
        f'<footer><b>{esc(title)}</b><br>{len(rows)} videos \u00b7 generated {date.today().isoformat()}</footer>'
        '<button class="totop" id="gTop" aria-label="back to top">\u2191</button>'
        f'<script>{GUIDE_JS}</script></body></html>'
    )


def build(path=None, title=None, rows=None, map_href="video_map.html"):
    path = str(path or config.GUIDE_PATH)
    data = store.all_videos() if rows is None else rows
    html_doc = build_guide(data, title, map_href)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return path
