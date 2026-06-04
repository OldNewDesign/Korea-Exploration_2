"""Turn location text into coordinates. Uses the Google Geocoding API when a key
is set (best for messy / Korean addresses), otherwise OpenStreetMap's free
Nominatim service. If Google errors or finds nothing, it AUTOMATICALLY falls
back to OpenStreetMap. Successful lookups are cached; failures are NOT cached, so
they retry on the next run (this also self-heals caches poisoned by older
versions). Use probe() to see exactly why a lookup fails."""
import json
import time
import urllib.parse
import urllib.request
from . import config, store

_last = [0.0]


def _interval():
    # Google tolerates higher QPS; Nominatim asks for <=1/sec.
    return 0.05 if config.use_google_geocode() else config.GEO_MIN_INTERVAL


def _rate_limit():
    iv = _interval()
    dt = time.time() - _last[0]
    if dt < iv:
        time.sleep(iv - dt)
    _last[0] = time.time()


def _clean(q):
    q = (q or "").replace("\u2014", ",").replace("\u2013", ",")
    return " ".join(q.split()).strip(" ,")


def _candidates(q):
    """Try the full string first, then a simplified region-only version."""
    cands = [q]
    parts = [p.strip() for p in q.split(",") if p.strip()]
    if len(parts) > 2:
        cands.append(", ".join(parts[-2:]))   # e.g. "Gangnam-gu, Seoul"
    return cands


def _query_google(q):
    url = "https://maps.googleapis.com/maps/api/geocode/json?" + urllib.parse.urlencode(
        {"address": q, "key": config.GOOGLE_MAPS_API_KEY}
    )
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.load(resp)
    status = data.get("status")
    if status == "OK" and data.get("results"):
        r = data["results"][0]
        loc = r["geometry"]["location"]
        return float(loc["lat"]), float(loc["lng"]), r.get("formatted_address", "")
    if status in ("OVER_QUERY_LIMIT", "REQUEST_DENIED", "INVALID_REQUEST"):
        raise RuntimeError(f"Google geocode {status}: {data.get('error_message','')}")
    return None  # ZERO_RESULTS


def _query_nominatim(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1}
    )
    req = urllib.request.Request(url, headers={"User-Agent": config.GEO_USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        arr = json.load(resp)
    if arr:
        return float(arr[0]["lat"]), float(arr[0]["lon"]), arr[0].get("display_name", "")
    return None


def _query(q):
    return _query_google(q) if config.use_google_geocode() else _query_nominatim(q)


def geocode(location):
    """Return (lat, lng, display_name) or None. Trusts cached hits; ignores any
    cached misses (so failures from older versions retry); falls back to OSM."""
    q = _clean(location)
    if not q:
        return None

    cached = store.geocache_get(q)
    if cached is not None and cached[0] == "hit":
        return (cached[1], cached[2], cached[3])
    # NOTE: cached "miss" entries are intentionally ignored and re-queried.

    used_google = config.use_google_geocode()
    result = None
    for cand in _candidates(q):
        _rate_limit()
        try:
            result = _query(cand)
        except Exception:
            result = None
        if result:
            break

    # If Google errored or found nothing, try the free OSM service before giving up.
    if result is None and used_google:
        for cand in _candidates(q):
            _rate_limit()
            try:
                result = _query_nominatim(cand)
            except Exception:
                result = None
            if result:
                break

    if result:
        store.geocache_set(q, result[0], result[1], result[2])
        return result
    return None   # do NOT cache failures -> they retry next run


def probe(location):
    """Diagnostic: try one lookup and report exactly what happened (incl. errors)."""
    q = _clean(location)
    info = {"query": q, "provider": "google" if config.use_google_geocode() else "osm"}
    if not q:
        return {**info, "ok": False, "error": "empty location"}
    try:
        r = _query(q)
        if r:
            return {**info, "ok": True, "result": {"lat": r[0], "lng": r[1], "matched": r[2]}}
        # google zero-results: show OSM fallback outcome too
        if config.use_google_geocode():
            try:
                r2 = _query_nominatim(q)
                if r2:
                    return {**info, "ok": True, "via": "osm-fallback",
                            "result": {"lat": r2[0], "lng": r2[1], "matched": r2[2]}}
            except Exception as e:
                return {**info, "ok": False, "error": f"osm fallback failed: {e}"}
        return {**info, "ok": False, "note": "no results from provider"}
    except Exception as e:
        return {**info, "ok": False, "error": str(e)}
