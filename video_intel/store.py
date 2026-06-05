"""SQLite is the source of truth. Excel + the HTML guide are exports from it."""
import sqlite3
from datetime import datetime
from . import config

COLUMNS = [
    "url", "platform", "cls", "creator", "title", "topic", "sub_category",
    "summary", "caption_english", "caption_original", "transcript_original",
    "detected_language", "location", "hashtags", "keywords", "upload_date",
    "duration", "view_count", "like_count", "comment_count", "usefulness",
    "action", "confidence", "needs_review", "audio_file", "processed_at",
]


def connect():
    config.ensure_dirs()
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = connect()
    con.execute("""
        CREATE TABLE IF NOT EXISTS videos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            platform TEXT, cls TEXT, creator TEXT, title TEXT,
            topic TEXT, sub_category TEXT, summary TEXT,
            caption_english TEXT, caption_original TEXT, transcript_original TEXT,
            detected_language TEXT, location TEXT, hashtags TEXT, keywords TEXT,
            upload_date TEXT, duration INTEGER,
            view_count INTEGER, like_count INTEGER, comment_count INTEGER,
            usefulness INTEGER, action TEXT, confidence REAL, needs_review INTEGER,
            audio_file TEXT, processed_at TEXT, lat REAL, lng REAL
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS errors(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, stage TEXT, message TEXT, ts TEXT
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS geocache(
            query TEXT PRIMARY KEY, lat REAL, lng REAL, display TEXT, ts TEXT
        )""")
    # migrate older DBs that predate lat/lng/shared
    have = {r["name"] for r in con.execute("PRAGMA table_info(videos)")}
    if "lat" not in have:
        con.execute("ALTER TABLE videos ADD COLUMN lat REAL")
    if "lng" not in have:
        con.execute("ALTER TABLE videos ADD COLUMN lng REAL")
    if "shared" not in have:
        con.execute("ALTER TABLE videos ADD COLUMN shared INTEGER DEFAULT 0")
    con.commit()
    con.close()


def set_shared(url, value):
    con = connect()
    con.execute("UPDATE videos SET shared=? WHERE url=?", (1 if value else 0, url))
    con.commit()
    con.close()


def clear_geocache(misses_only=False):
    con = connect()
    if misses_only:
        con.execute("DELETE FROM geocache WHERE lat IS NULL")
    else:
        con.execute("DELETE FROM geocache")
    con.commit()
    con.close()


def shared_videos():
    con = connect()
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM videos WHERE shared=1 ORDER BY topic, id")]
    con.close()
    return rows


def update_coords(url, lat, lng):
    con = connect()
    con.execute("UPDATE videos SET lat=?, lng=? WHERE url=?", (lat, lng, url))
    con.commit()
    con.close()


def update_location(url, location):
    """Set a video's location text and clear its old pin so it re-geocodes."""
    con = connect()
    con.execute("UPDATE videos SET location=?, lat=NULL, lng=NULL WHERE url=?",
                (location, url))
    con.commit()
    con.close()


def geocache_get(query):
    """None = never tried; ('miss',) = tried, no result; ('hit', lat, lng, display)."""
    con = connect()
    row = con.execute("SELECT lat, lng, display FROM geocache WHERE query=?", (query,)).fetchone()
    con.close()
    if row is None:
        return None
    if row["lat"] is None:
        return ("miss",)
    return ("hit", row["lat"], row["lng"], row["display"])


def geocache_set(query, lat, lng, display):
    con = connect()
    con.execute(
        "INSERT INTO geocache (query, lat, lng, display, ts) VALUES (?,?,?,?,?) "
        "ON CONFLICT(query) DO UPDATE SET lat=excluded.lat, lng=excluded.lng, "
        "display=excluded.display, ts=excluded.ts",
        (query, lat, lng, display or "", datetime.now().isoformat(timespec="seconds")),
    )
    con.commit()
    con.close()


def exists(url: str) -> bool:
    con = connect()
    row = con.execute("SELECT 1 FROM videos WHERE url=?", (url,)).fetchone()
    con.close()
    return row is not None


def upsert_video(row: dict):
    data = {c: row.get(c, "") for c in COLUMNS}
    data["processed_at"] = datetime.now().isoformat(timespec="seconds")
    cols = ", ".join(COLUMNS)
    ph = ", ".join("?" for _ in COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "url")
    sql = (f"INSERT INTO videos ({cols}) VALUES ({ph}) "
           f"ON CONFLICT(url) DO UPDATE SET {updates}")
    con = connect()
    con.execute(sql, [data[c] for c in COLUMNS])
    con.commit()
    con.close()


def log_error(url: str, stage: str, message: str):
    con = connect()
    con.execute("INSERT INTO errors (url, stage, message, ts) VALUES (?,?,?,?)",
                (url, stage, str(message)[:1000], datetime.now().isoformat(timespec="seconds")))
    con.commit()
    con.close()


def all_videos():
    con = connect()
    rows = [dict(r) for r in con.execute("SELECT * FROM videos ORDER BY topic, id")]
    con.close()
    return rows


def clear_errors():
    con = connect()
    con.execute("DELETE FROM errors")
    con.commit()
    con.close()


def all_errors():
    con = connect()
    rows = [dict(r) for r in con.execute("SELECT * FROM errors ORDER BY id")]
    con.close()
    return rows
