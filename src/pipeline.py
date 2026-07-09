"""End-to-end voice pipeline: audio in -> Saaras STT -> agent -> Bulbul TTS -> audio out.

Captures per-stage latency (asr / llm / tts / total) on every turn. Those timings are
what the eval harness aggregates into p50/p95, and what the UI shows the user.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import config
from .agent import run_agent
from .sarvam_client import synthesize, transcribe


@dataclass
class Turn:
    transcript: str = ""
    reply: str = ""
    audio: bytes = b""
    tools_used: list[str] = field(default_factory=list)
    asr_ms: float = 0.0
    llm_ms: float = 0.0
    tts_ms: float = 0.0
    total_ms: float = 0.0

    def timing_summary(self) -> str:
        return (f"ASR {self.asr_ms:.0f} ms · LLM {self.llm_ms:.0f} ms · "
                f"TTS {self.tts_ms:.0f} ms · total {self.total_ms:.0f} ms")


def run_voice_turn(audio: bytes, lang: str = config.DEFAULT_LANG,
                   history: list[dict] | None = None) -> Turn:
    """Full spoken turn: raw audio bytes -> spoken reply bytes, timed at each hop."""
    t_start = time.perf_counter()

    transcript, asr_ms = transcribe(audio)
    agent_out = run_agent(transcript, history=history)
    reply = agent_out["reply"]
    reply_audio, tts_ms = synthesize(reply, lang=lang)

    total_ms = (time.perf_counter() - t_start) * 1000.0
    return Turn(
        transcript=transcript, reply=reply, audio=reply_audio,
        tools_used=agent_out["tool_calls"],
        asr_ms=asr_ms, llm_ms=agent_out["llm_ms"], tts_ms=tts_ms, total_ms=total_ms,
    )


def run_text_turn(text: str, lang: str = config.DEFAULT_LANG,
                  speak: bool = False, history: list[dict] | None = None) -> Turn:
    """Text-in variant (skips ASR). Used by the eval harness and quick testing."""
    t_start = time.perf_counter()
    agent_out = run_agent(text, history=history)
    reply = agent_out["reply"]
    audio, tts_ms = (synthesize(reply, lang=lang) if speak else (b"", 0.0))
    total_ms = (time.perf_counter() - t_start) * 1000.0
    return Turn(
        transcript=text, reply=reply, audio=audio, tools_used=agent_out["tool_calls"],
        asr_ms=0.0, llm_ms=agent_out["llm_ms"], tts_ms=tts_ms, total_ms=total_ms,
    )
