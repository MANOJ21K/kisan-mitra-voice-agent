"""Metrics tests: WER + latency percentiles. Fully key-free."""
from __future__ import annotations

from eval.metrics import latency_stats, percentile, word_error_rate


def test_wer_perfect_match():
    assert word_error_rate("the cat sat", "the cat sat") == 0.0


def test_wer_substitution():
    assert abs(word_error_rate("the cat sat", "the cat ran") - 1 / 3) < 1e-9


def test_wer_deletion():
    assert abs(word_error_rate("a b c d", "a b c") - 1 / 4) < 1e-9


def test_wer_insertion():
    assert abs(word_error_rate("a b c", "a b c d") - 1 / 3) < 1e-9


def test_wer_indic_script():
    assert word_error_rate("टमाटर का भाव", "टमाटर का भाव") == 0.0


def test_wer_empty_reference():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("", "something") == 1.0


def test_percentile_interpolation():
    assert abs(percentile([10, 20, 30, 40], 50) - 25.0) < 1e-9


def test_percentile_edges():
    assert percentile([], 50) == 0.0
    assert percentile([42], 95) == 42


def test_latency_stats_shape():
    s = latency_stats([120, 180, 95, 260, 140])
    assert s["n"] == 5
    assert s["max"] == 260
    assert s["p50"] > 0 and s["p95"] >= s["p50"]


def test_latency_stats_empty():
    s = latency_stats([])
    assert s == {"n": 0, "p50": 0.0, "p95": 0.0, "mean": 0.0, "max": 0.0}
