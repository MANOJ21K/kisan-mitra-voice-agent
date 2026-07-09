"""Run the Kisan Mitra agent over the golden set and report quality + latency.

Metrics:
  - tool accuracy   : did the agent call the expected tool(s)?
  - answer accuracy : did the reply contain the expected grounded fact(s)?
  - latency         : per-stage p50/p95 across the whole set (LLM, +TTS if --speak)
  - WER (optional)   : if a case carries an audio file + reference, score ASR too

Usage:
  python eval/run_eval.py                 # text-in, quality + LLM latency
  python eval/run_eval.py --speak         # also synthesise replies (adds TTS latency)
  python eval/run_eval.py --n 5           # first N cases only (save credits)

Needs SARVAM_API_KEY. The metrics module (eval/metrics.py) runs key-free on its own.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.metrics import latency_stats, word_error_rate  # noqa: E402
from src.pipeline import run_text_turn  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "golden_set.jsonl")


def load_cases(limit: int | None) -> list[dict]:
    cases = []
    with open(GOLDEN, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases[:limit] if limit else cases


def tool_match(expected: list[str], got: list[str]) -> bool:
    """Every expected tool must have been called (order/extra calls ignored)."""
    got_set = set(got)
    return all(t in got_set for t in expected)


def _norm_digits(s: str) -> str:
    """Drop thousands separators so '1,800' and '1800' compare equal."""
    return re.sub(r"(?<=\d)[,\s](?=\d)", "", s.lower())


def keyword_hit(reply: str, keywords: list[str]) -> bool:
    """Grounded-fact check: at least one expected keyword appears in the reply.

    Digit-normalised so number formatting ('1,800' vs '1800') doesn't cause a miss.
    """
    if not keywords:
        return True
    low = _norm_digits(reply)
    return any(_norm_digits(k) in low for k in keywords)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speak", action="store_true", help="also run TTS (measures TTS latency)")
    ap.add_argument("--n", type=int, default=None, help="only the first N cases")
    args = ap.parse_args()

    cases = load_cases(args.n)
    tool_ok = ans_ok = 0
    llm_lat, tts_lat, total_lat, wers = [], [], [], []
    rows = []

    for c in cases:
        turn = run_text_turn(c["query"], lang=c.get("lang", "hi-IN"), speak=args.speak)
        t_ok = tool_match(c.get("expect_tools", []), turn.tools_used)
        a_ok = keyword_hit(turn.reply, c.get("expect_keywords", []))
        tool_ok += t_ok
        ans_ok += a_ok
        llm_lat.append(turn.llm_ms)
        total_lat.append(turn.total_ms)
        if args.speak:
            tts_lat.append(turn.tts_ms)
        if c.get("audio") and c.get("reference"):  # optional ASR scoring
            from src.sarvam_client import transcribe
            with open(c["audio"], "rb") as fh:
                hyp, _ = transcribe(fh.read())
            wers.append(word_error_rate(c["reference"], hyp))

        rows.append((c["id"], "✓" if t_ok else "✗", "✓" if a_ok else "✗",
                     f"{turn.llm_ms:.0f}", ",".join(turn.tools_used) or "-"))

    n = len(cases)
    print(f"\nKisan Mitra eval — {n} cases\n" + "=" * 62)
    print(f"{'case':<22}{'tool':<6}{'ans':<6}{'llm_ms':<9}tools_used")
    print("-" * 62)
    for r in rows:
        print(f"{r[0]:<22}{r[1]:<6}{r[2]:<6}{r[3]:<9}{r[4]}")
    print("-" * 62)
    print(f"tool accuracy   : {tool_ok}/{n}  ({100*tool_ok/n:.0f}%)")
    print(f"answer accuracy : {ans_ok}/{n}  ({100*ans_ok/n:.0f}%)")

    ls = latency_stats(llm_lat)
    print(f"LLM latency     : p50 {ls['p50']:.0f} ms · p95 {ls['p95']:.0f} ms · max {ls['max']:.0f} ms")
    if args.speak and tts_lat:
        ts = latency_stats(tts_lat)
        print(f"TTS latency     : p50 {ts['p50']:.0f} ms · p95 {ts['p95']:.0f} ms")
    tl = latency_stats(total_lat)
    print(f"total latency   : p50 {tl['p50']:.0f} ms · p95 {tl['p95']:.0f} ms")
    if wers:
        ws = latency_stats(wers)
        print(f"ASR WER         : p50 {ws['p50']:.2f} · mean {ws['mean']:.2f}")
    print()


if __name__ == "__main__":
    main()
