"""LLM-as-judge for Kisan Mitra replies, running on Sarvam's stronger model.

A larger model (sarvam-105b) grades the smaller agent's (sarvam-30b) answers — a
standard eval pattern, kept entirely inside Sarvam's stack. The judge sees the
farmer's question, the raw tool outputs the agent had, and the agent's reply, then
scores two things a farmer advisory must get right:

  - faithfulness      : does the reply stick to the tool data (no invented prices,
                        dates, or scheme amounts)?  1-5
  - spoken_friendly   : is it short, clear, and natural to hear read aloud?  1-5

It returns structured JSON so run_eval.py can aggregate mean/min. The judge is
optional (run_eval.py --judge); the harness works without it.
"""
from __future__ import annotations

import json

from openai import OpenAI

from src import config

_oai: OpenAI | None = None

JUDGE_SYSTEM = (
    "You are a strict evaluator of an Indian farmer-advisory voice assistant. "
    "You will be given the farmer's question, the exact tool outputs the assistant "
    "had available, and the assistant's reply. Judge only what is shown; do not use "
    "outside knowledge of prices or weather. Return ONLY a JSON object with keys: "
    "faithfulness (int 1-5: 5 = every fact in the reply is supported by the tool "
    "outputs and nothing is invented; 1 = fabricated or contradicts the tools), "
    "spoken_friendly (int 1-5: 5 = concise, clear, natural read aloud in 2-4 "
    "sentences; 1 = long, robotic, or hard to follow), and reason (one short string). "
    "If the tool outputs contain an error and the reply honestly relays that, "
    "faithfulness should be high."
)


def _client() -> OpenAI:
    global _oai
    if _oai is None:
        _oai = OpenAI(api_key=config.require_key(), base_url=config.SARVAM_OPENAI_BASE_URL)
    return _oai


def judge_reply(query: str, reply: str, tool_results: list[dict]) -> dict:
    """Score one reply. Returns {faithfulness, spoken_friendly, reason}.

    On any judge/parse failure returns the scores as None with an error reason, so
    a flaky judge call never crashes the eval run.
    """
    payload = {
        "farmer_question": query,
        "tool_outputs": tool_results or "(no tools were called)",
        "assistant_reply": reply,
    }
    try:
        resp = _client().chat.completions.create(
            model=config.JUDGE_MODEL,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(_strip_fences(raw))
        return {
            "faithfulness": _clamp(data.get("faithfulness")),
            "spoken_friendly": _clamp(data.get("spoken_friendly")),
            "reason": str(data.get("reason", ""))[:200],
        }
    except Exception as e:  # a judge failure must not fail the eval run
        return {"faithfulness": None, "spoken_friendly": None, "reason": f"judge error: {e}"}


def _strip_fences(s: str) -> str:
    """Tolerate a model that wraps JSON in ```json ... ``` fences."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1].removeprefix("json").strip()
    return s


def _clamp(v) -> int | None:
    try:
        return max(1, min(5, int(v)))
    except (TypeError, ValueError):
        return None
