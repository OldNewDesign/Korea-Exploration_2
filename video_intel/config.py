"""Central configuration: paths, environment, models, categories."""
import os
from pathlib import Path

# ---- folders -------------------------------------------------------------
# Default to the project root (the folder that contains the video_intel package),
# so the CLI and the Streamlit app always use the SAME output/ and database no
# matter which directory you launch them from. Override with VIP_BASE_DIR.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_DIR     = Path(os.environ.get("VIP_BASE_DIR", _PROJECT_ROOT)).resolve()
INPUT_DIR    = BASE_DIR / "input"
DOWNLOADS    = BASE_DIR / "downloads"
AUDIO_DIR    = BASE_DIR / "audio"
TRANSCRIPTS  = BASE_DIR / "transcripts"
OUTPUT_DIR   = BASE_DIR / "output"
DB_PATH      = OUTPUT_DIR / "video_intel.db"
EXCEL_PATH   = OUTPUT_DIR / "video_library.xlsx"
GUIDE_PATH   = OUTPUT_DIR / "video_guide.html"
MAP_PATH     = OUTPUT_DIR / "video_map.html"
SHARE_DIR    = BASE_DIR / "docs"   # ready to publish via GitHub Pages

# ---- geocoding ------------------------------------------------------------
# Google Geocoding is used when GOOGLE_MAPS_API_KEY is set (better with messy /
# Korean addresses); otherwise it falls back to OpenStreetMap (free, no key).
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
# "auto" -> google if a key is set, else osm. Force with "google" or "osm".
GEO_PROVIDER = os.environ.get("VIP_GEO_PROVIDER", "auto").lower()
# Map render provider, same "auto"/"google"/"osm" logic.
MAP_PROVIDER = os.environ.get("VIP_MAP_PROVIDER", "auto").lower()

# Nominatim (OSM) etiquette: <=1 request/sec + a descriptive User-Agent.
GEO_USER_AGENT   = os.environ.get("VIP_GEO_AGENT", "video-intel-pipeline/1.0 (personal video library)")
GEO_MIN_INTERVAL = float(os.environ.get("VIP_GEO_INTERVAL", "1.1"))


def use_google_geocode():
    if GEO_PROVIDER == "google":
        return True
    if GEO_PROVIDER == "osm":
        return False
    return bool(GOOGLE_MAPS_API_KEY)


def use_google_map():
    if MAP_PROVIDER == "google":
        return True
    if MAP_PROVIDER == "osm":
        return False
    return bool(GOOGLE_MAPS_API_KEY)

# ---- AI ------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Change to whatever model you have access to (see https://docs.claude.com/en/api/overview)
ANALYZE_MODEL     = os.environ.get("VIP_MODEL", "claude-sonnet-4-6")

# Whisper model size: tiny | base | small | medium | large-v3 | turbo
WHISPER_MODEL     = os.environ.get("VIP_WHISPER_MODEL", "small")

# ---- categorization ------------------------------------------------------
# Defaults mirror the Korea & Seoul guide. Last item is the fallback bucket.
CATEGORIES = [
    "Places to Eat", "Cafes & Desserts", "Recipes & Cooking", "Hikes & Nature",
    "Activities & Experiences", "Animal Cafes & Zoos", "Museums & Art",
    "Historic & Cultural", "Beauty & Wellness", "Workouts & Fitness",
    "Running Spots & Gear", "Shopping & Markets", "DIY Crafts & Photobooths",
    "Travel Tips & Guides", "Fragrance & Cologne", "Watches & Accessories", "Other",
]

GUIDE_TITLE = os.environ.get("VIP_GUIDE_TITLE", "My Video Guide")


def ensure_dirs():
    for d in (INPUT_DIR, DOWNLOADS, AUDIO_DIR, TRANSCRIPTS, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
