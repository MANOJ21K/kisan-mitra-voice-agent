"""Pure-Python metrics for the eval harness: WER and latency percentiles.

No API key needed to run this file — it ships a self-test in __main__ so the metrics
can be verified in isolation before spending Sarvam credits on a full run.
"""
from __future__ import annotations

import re
import unicodedata


def _norm(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace. Works for Indic scripts too."""
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text.split()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """WER = (substitutions + insertions + deletions) / reference-word-count.

    Levenshtein distance over word tokens. Returns 0.0 for a perfect match, and can
    exceed 1.0 when the hypothesis is much longer than the reference.
    """
    ref, hyp = _norm(reference), _norm(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    # Classic DP edit-distance table over words.
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cost = 0 if r == h else 1
            cur[j] = min(prev[j] + 1,        # deletion
                         cur[j - 1] + 1,     # insertion
                         prev[j - 1] + cost)  # substitution / match
        prev = cur
    return prev[len(hyp)] / len(ref)


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (pct in 0..100). Empty -> 0.0."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (pct / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def latency_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50": 0.0, "p95": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "n": len(values),
        "p50": percentile(values, 50),
        "p95": percentile(values, 95),
        "mean": sum(values) / len(values),
        "max": max(values),
    }


if __name__ == "__main__":
    # Self-test: verifiable without any API key.
    assert word_error_rate("the cat sat", "the cat sat") == 0.0
    assert abs(word_error_rate("the cat sat", "the cat ran") - 1 / 3) < 1e-9
    assert abs(word_error_rate("a b c d", "a b c") - 1 / 4) < 1e-9  # one deletion
    assert word_error_rate("टमाटर का भाव", "टमाटर का भाव") == 0.0
    assert abs(percentile([10, 20, 30, 40], 50) - 25.0) < 1e-9
    print("metrics self-test passed ✓")
    demo = [120, 180, 95, 260, 140, 310, 155]
    print("latency demo:", {k: round(v, 1) for k, v in latency_stats(demo).items()})
