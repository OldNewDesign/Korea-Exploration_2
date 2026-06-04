"""Audio step: normalize any media file to 16 kHz mono WAV for Whisper."""
import shutil
import subprocess
from pathlib import Path
from . import config


class AudioError(Exception):
    pass


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def to_wav(input_path: str, stem: str) -> str:
    """Convert input media to transcripts-friendly WAV. Returns output path."""
    if not have_ffmpeg():
        raise AudioError("ffmpeg not found on PATH. Install it (e.g. `brew install ffmpeg`).")
    if not input_path or not Path(input_path).exists():
        raise AudioError(f"input audio missing: {input_path}")

    config.ensure_dirs()
    out = config.AUDIO_DIR / f"{stem}.wav"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-ac", "1", "-ar", "16000", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        raise AudioError(f"ffmpeg failed: {proc.stderr[-400:]}")
    return str(out)
