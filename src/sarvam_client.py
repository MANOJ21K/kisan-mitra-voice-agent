"""Thin wrappers over Sarvam's speech + translate APIs, with latency capture.

Each call returns (result, elapsed_ms) so the pipeline and eval harness can track
per-stage latency without re-instrumenting everything.
"""
from __future__ import annotations

import base64
import io
import time
from typing import BinaryIO

from sarvamai import SarvamAI

from . import config

_client: SarvamAI | None = None


def client() -> SarvamAI:
    global _client
    if _client is None:
        _client = SarvamAI(api_subscription_key=config.require_key())
    return _client


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, (time.perf_counter() - t0) * 1000.0


def transcribe(audio: BinaryIO | bytes, mode: str = "transcribe") -> tuple[str, float]:
    """Saaras v3 speech-to-text. Auto-detects the Indian language and returns text.

    mode: "transcribe" (native script) | "translate" (to English) | "codemix" | ...
    """
    f = io.BytesIO(audio) if isinstance(audio, (bytes, bytearray)) else audio
    resp, ms = _timed(lambda: client().speech_to_text.transcribe(
        file=f, model=config.STT_MODEL, mode=mode,
    ))
    text = getattr(resp, "transcript", None) or getattr(resp, "text", "") or ""
    return text.strip(), ms


def synthesize(text: str, lang: str = config.DEFAULT_LANG) -> tuple[bytes, float]:
    """Bulbul v3 text-to-speech. Returns decoded audio bytes (wav/mp3)."""
    resp, ms = _timed(lambda: client().text_to_speech.convert(
        text=text,
        target_language_code=lang,
        model=config.TTS_MODEL,
        speaker=config.TTS_SPEAKER,
    ))
    # SDK returns base64-encoded audio (usually a list of chunks).
    audios = getattr(resp, "audios", None) or getattr(resp, "audio", None)
    if isinstance(audios, list):
        raw = b"".join(base64.b64decode(a) for a in audios)
    elif isinstance(audios, str):
        raw = base64.b64decode(audios)
    else:
        raw = bytes(audios or b"")
    return raw, ms


def translate(text: str, target: str, source: str = "auto") -> tuple[str, float]:
    """Sarvam-Translate. Used to normalise the golden set / support English replies."""
    resp, ms = _timed(lambda: client().text.translate(
        input=text, source_language_code=source, target_language_code=target,
    ))
    out = getattr(resp, "translated_text", None) or getattr(resp, "output", "") or ""
    return out.strip(), ms
