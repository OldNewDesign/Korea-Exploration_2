"""Map a URL to a platform label + CSS class (matches the web app)."""
import re

_RULES = [
    (re.compile(r"instagram\.com|instagr\.am", re.I), ("Instagram", "ig")),
    (re.compile(r"tiktok\.com", re.I),                ("TikTok",    "tt")),
    (re.compile(r"youtube\.com|youtu\.be", re.I),     ("YouTube",   "yt")),
    (re.compile(r"facebook\.com|fb\.watch|fb\.com", re.I), ("Facebook", "fb")),
    (re.compile(r"twitter\.com|x\.com", re.I),        ("X",         "xx")),
    (re.compile(r"reddit\.com|redd\.it", re.I),       ("Reddit",    "rd")),
]


def detect_platform(url: str):
    u = url or ""
    for rx, val in _RULES:
        if rx.search(u):
            return val
    return ("Other", "other")


def watch_label(platform: str) -> str:
    return "Open link \u2192" if platform == "Other" else f"Watch on {platform} \u2192"
