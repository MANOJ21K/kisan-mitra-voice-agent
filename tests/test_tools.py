"""Tool tests. Network is fully mocked — no live API calls, no API key needed.

Covers the real-API tools (get_weather via Open-Meteo, get_mandi_price via
Agmarknet) with faked HTTP responses, the curated tools, and the dispatch guards.
"""
from __future__ import annotations

import requests

from src import tools


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


# --- get_weather (Open-Meteo) ---------------------------------------------

_GEO = {"results": [{"name": "Kolar", "admin1": "Karnataka",
                     "latitude": 13.13, "longitude": 78.13}]}


def _forecast(rain):
    return {"daily": {
        "time": ["2026-07-09", "2026-07-10", "2026-07-11"],
        "precipitation_sum": rain,
        "temperature_2m_max": [30, 31, 32],
        "temperature_2m_min": [21, 22, 23],
        "weathercode": [3, 95, 0],
    }}


def test_weather_wet_day_advises_dry_day(monkeypatch):
    seq = iter([FakeResp(_GEO), FakeResp(_forecast([0.0, 12.0, 0.0]))])
    monkeypatch.setattr(requests, "get", lambda *a, **k: next(seq))
    out = tools.get_weather("Kolar")
    assert out["location"].startswith("Kolar")
    assert len(out["forecast"]) == 3
    assert out["forecast"][1]["rain_mm"] == 12.0
    # rain tomorrow -> advice should steer to a dry day, not tomorrow
    assert "tomorrow" in out["advice"]


def test_weather_all_dry_is_safe_to_spray(monkeypatch):
    seq = iter([FakeResp(_GEO), FakeResp(_forecast([0.0, 1.0, 0.0]))])
    monkeypatch.setattr(requests, "get", lambda *a, **k: next(seq))
    out = tools.get_weather("Kolar")
    assert "safe to spray" in out["advice"].lower()


def test_weather_unknown_place_errors(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp({"results": []}))
    out = tools.get_weather("Nowhereville")
    assert "error" in out


def test_weather_empty_location_errors():
    assert "error" in tools.get_weather("   ")


def test_weather_network_failure_returns_error(monkeypatch):
    def boom(*a, **k):
        raise requests.RequestException("connection reset")
    monkeypatch.setattr(requests, "get", boom)
    out = tools.get_weather("Kolar")
    assert "error" in out and "unavailable" in out["error"].lower()


# --- get_mandi_price (Agmarknet) ------------------------------------------

_RECORDS = {"records": [
    {"commodity": "Tomato", "state": "Karnataka", "district": "Kolar",
     "market": "Kolar", "variety": "Local", "arrival_date": "09/07/2026",
     "min_price": "800", "modal_price": "1200", "max_price": "1600"},
    {"commodity": "Tomato", "market": "Bengaluru", "min_price": 1000,
     "modal_price": 1450, "max_price": 1900, "arrival_date": "09/07/2026"},
]}


def test_mandi_parses_prices_and_counts_markets(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp(_RECORDS))
    out = tools.get_mandi_price("tomato")
    assert out["min"] == 800 and out["modal"] == 1200 and out["max"] == 1600
    assert out["unit"] == "INR/quintal"
    assert out["other_markets_reporting"] == 1


def test_mandi_empty_commodity_errors():
    assert "error" in tools.get_mandi_price("")


def test_mandi_no_records_errors(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResp({"records": []}))
    out = tools.get_mandi_price("unobtanium")
    assert "error" in out


def test_mandi_market_filter_retries_unfiltered(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        # first call (with market filter) -> empty; retry (no filter) -> records
        return FakeResp({"records": []} if "filters[market]" in params else _RECORDS)

    monkeypatch.setattr(requests, "get", fake_get)
    out = tools.get_mandi_price("tomato", market="TinyVillage")
    assert out["modal"] == 1200          # got data from the retry
    assert len(calls) == 2               # proved the fallback fired


def test_mandi_network_failure_returns_error(monkeypatch):
    def boom(*a, **k):
        raise requests.RequestException("429 Too Many Requests")
    monkeypatch.setattr(requests, "get", boom)
    out = tools.get_mandi_price("tomato")
    assert "error" in out


# --- curated tools ---------------------------------------------------------

def test_crop_advisory_known_and_unknown():
    assert "nitrogen" in tools.get_crop_advisory("wheat")["advisory"].lower()
    assert "no advisory" in tools.get_crop_advisory("banana")["advisory"].lower()


def test_scheme_alias_matching():
    assert tools.get_govt_scheme("I need a crop loan")["scheme"] == "kcc"
    assert tools.get_govt_scheme("flood damage insurance")["scheme"] == "fasal bima"
    assert tools.get_govt_scheme("income support")["scheme"] == "pm-kisan"
    assert "no matching scheme" in tools.get_govt_scheme("free tractor")["details"].lower()


# --- dispatch guards -------------------------------------------------------

def test_dispatch_unknown_tool():
    assert "Unknown tool" in tools.dispatch("no_such_tool", {})["error"]


def test_dispatch_bad_arguments():
    out = tools.dispatch("get_crop_advisory", {"wrong_kwarg": "x"})
    assert "error" in out and "Bad arguments" in out["error"]


def test_registry_schemas_match_functions():
    for name, entry in tools.REGISTRY.items():
        assert entry["schema"]["function"]["name"] == name
        assert callable(entry["fn"])
