"""TTS de navegación: Piper Maider (euskera, HiTZ/Aholab vía itzune).

Lazy-load: no se carga el ONNX al arrancar el servicio semántico (RAM).
Sin modelo o sin piper → el caller recibe unavailable, no se finge voz.
"""
from __future__ import annotations

import os
import tempfile
import wave
from pathlib import Path

PIPER_DIR = Path(
    os.environ.get(
        "EMAP_PIPER_DIR",
        str(Path(__file__).resolve().parent.parent / "tts"),
    )
).expanduser()
PIPER_MODEL = os.environ.get("EMAP_PIPER_MODEL", "eu-maider-medium").strip()
PIPER_REPO = os.environ.get("EMAP_PIPER_REPO", "itzune/maider-tts").strip()

_piper = None
_piper_error: str | None = None


def _clamp(text: str, max_len: int = 280) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def model_paths() -> tuple[Path, Path]:
    return (
        PIPER_DIR / f"{PIPER_MODEL}.onnx",
        PIPER_DIR / f"{PIPER_MODEL}.onnx.json",
    )


def available() -> dict:
    onnx, cfg = model_paths()
    return {
        "engine": "piper-maider",
        "voice": "maider",
        "lang": "eu",
        "ready": onnx.is_file() and cfg.is_file() and _piper_error is None,
        "error": _piper_error,
    }


def _load():
    global _piper, _piper_error
    if _piper is not None:
        return _piper
    onnx, cfg = model_paths()
    if not onnx.is_file() or not cfg.is_file():
        _piper_error = f"falta modelo en {PIPER_DIR}"
        raise FileNotFoundError(_piper_error)
    from piper.voice import PiperVoice

    _piper = PiperVoice.load(str(onnx), config_path=str(cfg))
    _piper_error = None
    return _piper


def synthesize_eu(text: str) -> tuple[bytes, str, dict]:
    voice = _load()
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        with wave.open(tmp.name, "wb") as wav:
            voice.synthesize_wav(_clamp(text), wav)
        body = Path(tmp.name).read_bytes()
    return body, "audio/wav", {
        "engine": "piper-maider",
        "voice": "maider",
        "lang": "eu",
        "bytes": len(body),
    }
