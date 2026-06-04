"""Download step: pull metadata + best audio with yt-dlp.

yt-dlp supports thousands of sites. We only grab audio (cheaper/faster than the
full video, and all Whisper needs). Public/owned content only — do not bypass
logins, paywalls, or privacy settings.
"""
from pathlib import Path
from . import config


class DownloadError(Exception):
    pass


def _import_ytdlp():
    try:
        import yt_dlp  # noqa
        return yt_dlp
    except Exception as e:  # pragma: no cover
        raise DownloadError(
            "yt-dlp is not installed. Run: pip install -U yt-dlp"
        ) from e


def fetch(url: str, download_audio: bool = True) -> dict:
    """Return a metadata dict; if download_audio, also save best audio locally.

    Keys: id, title, description, uploader, uploader_id, duration, view_count,
    like_count, comment_count, repost_count, upload_date, webpage_url, tags,
    track/artist, audio_file (path or "").
    """
    yt_dlp = _import_ytdlp()
    config.ensure_dirs()
    outtmpl = str(config.DOWNLOADS / "%(extractor)s_%(id)s.%(ext)s")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreerrors": False,
        "outtmpl": outtmpl,
        "format": "bestaudio/best",
        "retries": 3,
        "socket_timeout": 30,
    }
    if not download_audio:
        opts["skip_download"] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=download_audio)
    except Exception as e:
        raise DownloadError(f"yt-dlp failed: {e}") from e

    if info is None:
        raise DownloadError("yt-dlp returned no info (private/expired/unsupported?)")

    audio_file = ""
    if download_audio:
        try:
            audio_file = ydl.prepare_filename(info)
            if not Path(audio_file).exists():
                # postprocessing may have changed the extension
                stem = Path(audio_file).with_suffix("")
                hits = list(config.DOWNLOADS.glob(stem.name + ".*"))
                audio_file = str(hits[0]) if hits else ""
        except Exception:
            audio_file = ""

    tags = info.get("tags") or info.get("hashtags") or []
    return {
        "id": info.get("id", ""),
        "title": info.get("title") or info.get("fulltitle") or "",
        "description": info.get("description") or "",
        "uploader": info.get("uploader") or info.get("channel") or "",
        "uploader_id": info.get("uploader_id") or info.get("channel_id") or "",
        "duration": info.get("duration") or 0,
        "view_count": info.get("view_count") or 0,
        "like_count": info.get("like_count") or 0,
        "comment_count": info.get("comment_count") or 0,
        "repost_count": info.get("repost_count") or 0,
        "upload_date": info.get("upload_date") or "",
        "webpage_url": info.get("webpage_url") or url,
        "tags": list(tags) if isinstance(tags, (list, tuple)) else [],
        "track": info.get("track") or "",
        "artist": info.get("artist") or "",
        "audio_file": audio_file,
    }
