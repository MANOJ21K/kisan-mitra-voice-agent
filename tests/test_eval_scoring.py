"""Tests for the eval scoring helpers (tool match + grounded-keyword check).

Importing eval.run_eval pulls in the pipeline, but these tests never call the
network or the models — they exercise the pure scoring functions only.
"""
from __future__ import annotations

from eval.run_eval import keyword_hit, tool_match


def test_tool_match_all_expected_present():
    assert tool_match(["get_weather"], ["get_weather"])
    assert tool_match(["get_weather"], ["get_weather", "get_mandi_price"])  # extra ok


def test_tool_match_missing_expected_fails():
    assert not tool_match(["get_weather", "get_mandi_price"], ["get_weather"])


def test_tool_match_empty_expected_is_pass():
    assert tool_match([], [])
    assert tool_match([], ["get_weather"])


def test_keyword_hit_digit_normalisation():
    # "1,800" in reply should satisfy an expected "1800" and vice versa
    assert keyword_hit("aaj bhaav 1,800 rupaye hai", ["1800"])
    assert keyword_hit("today it is 1800", ["1,800"])


def test_keyword_hit_case_insensitive_any():
    assert keyword_hit("PM-KISAN gives Rs 6000", ["6000", "nonexistent"])
    assert not keyword_hit("no relevant content", ["6000", "quintal"])


def test_keyword_hit_empty_keywords_is_pass():
    assert keyword_hit("anything at all", [])
