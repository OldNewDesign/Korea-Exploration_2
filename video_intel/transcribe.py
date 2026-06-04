"""Transcription step: local Whisper. Processes audio in 30s windows, so long
videos are fine. Set VIP_WHISPER_MODEL to trade speed for accuracy.

GPU: if a CUDA build of PyTorch is installed, Whisper runs on the GPU
automatically and this module enables fp16 for a good speedup (great on an
RTX 4090). Check your setup with:
    python -c "import torch; print(torch.cuda.is_available())"
If that prints False, install the CUDA build:
    pip install torch --index-url https://download.pytorch.org/whl/cu124
"""
from . import config

_MODEL = None
_CUDA = None


class TranscribeError(Exception):
    pass


def _cuda_available():
    global _CUDA
    if _CUDA is None:
        try:
            import torch
            _CUDA = bool(torch.cuda.is_available())
        except Exception:
            _CUDA = False
    return _CUDA


def _load():
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        import whisper
    except Exception as e:  # pragma: no cover
        raise TranscribeError(
            "openai-whisper not installed. Run: pip install -U openai-whisper"
        ) from e
    device = "cuda" if _cuda_available() else "cpu"
    _MODEL = whisper.load_model(config.WHISPER_MODEL, device=device)
    return _MODEL


def transcribe(wav_path: str) -> dict:
    """Return {'text': str, 'language': str}. Original-language transcript;
    translation/cleanup is handled later by the analyzer."""
    model = _load()
    try:
        # fp16 on GPU is faster and accurate enough; CPU must use fp32.
        result = model.transcribe(wav_path, fp16=_cuda_available())
    except Exception as e:
        raise TranscribeError(f"whisper failed: {e}") from e
    return {
        "text": (result.get("text") or "").strip(),
        "language": result.get("language") or "",
    }
