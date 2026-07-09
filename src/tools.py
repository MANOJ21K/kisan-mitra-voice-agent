"""Farmer-advisory tools for the Kisan Mitra agent.

Each tool is a plain Python function plus an OpenAI-style JSON schema. The same
registry backs both the live agent loop (src/agent.py) and the MCP server
(mcp_server/server.py), so there is exactly one source of truth for the tools.

Data honesty:
  - get_weather      -> live Open-Meteo (keyless) geocoding + forecast.
  - get_mandi_price  -> live data.gov.in Agmarknet daily mandi prices (free key).
  - get_crop_advisory / get_govt_scheme -> curated static reference data
    (agronomy practice and scheme facts are stable; not a live feed).

Tools never raise: on any network/API/lookup failure they return an {"error": ...}
dict. The agent's system prompt tells the model to relay that plainly to the farmer.
"""
from __future__ import annotations

import datetime as _dt

import requests

from . import config


def _get_json(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT_S)
    resp.raise_for_status()
    return resp.json()


_WMO = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain",
    71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Heavy rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}

# Rain (mm/day) at or above this makes foliar spraying pointless — it washes off.
_SPRAY_RAIN_THRESHOLD_MM = 5.0


def get_weather(location: str) -> dict:
    """Live 3-day outlook for a place, with spraying/irrigation advice derived
    from real forecast rainfall. Source: Open-Meteo (geocoding + forecast)."""
    place = (location or "").strip()
    if not place:
        return {"error": "No location given. Ask the farmer which village or town."}
    try:
        geo = _get_json(config.OPEN_METEO_GEOCODE_URL,
                        {"name": place, "count": 1, "country": "IN", "language": "en"})
        results = geo.get("results") or []
        if not results:
            return {"location": place,
                    "error": f"Could not find a place called '{place}' in India."}
        top = results[0]
        lat, lon = top["latitude"], top["longitude"]
        resolved = ", ".join(x for x in (top.get("name"), top.get("admin1")) if x)

        fc = _get_json(config.OPEN_METEO_FORECAST_URL, {
            "latitude": lat, "longitude": lon,
            "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,weathercode",
            "forecast_days": 3, "timezone": "auto",
        })
        daily = fc.get("daily") or {}
        days = daily.get("time") or []
        if not days:
            return {"location": resolved, "error": "Weather service returned no forecast."}

        rain = daily.get("precipitation_sum") or []
        labels = ["today", "tomorrow", "day_after"]
        forecast = []
        for i, day in enumerate(days):
            forecast.append({
                "day": labels[i] if i < len(labels) else day,
                "date": day,
                "high_c": (daily.get("temperature_2m_max") or [None])[i],
                "low_c": (daily.get("temperature_2m_min") or [None])[i],
                "rain_mm": rain[i] if i < len(rain) else None,
                "summary": _WMO.get((daily.get("weathercode") or [None])[i], "Unknown"),
            })

        wet = [f["day"] for f in forecast
               if isinstance(f["rain_mm"], (int, float)) and f["rain_mm"] >= _SPRAY_RAIN_THRESHOLD_MM]
        if not wet:
            advice = "No significant rain in the next 3 days — safe to spray or irrigate as needed."
        else:
            dry = [f["day"] for f in forecast if f["day"] not in wet]
            advice = (f"Rain expected {', '.join(wet)} — hold off on spraying then; "
                      + (f"spray on {dry[0]} instead." if dry else "wait for a dry day."))

        return {"location": resolved, "as_of": _dt.date.today().isoformat(),
                "forecast": forecast, "advice": advice}
    except requests.RequestException as e:
        return {"location": place, "error": f"Weather service unavailable: {e}"}


def get_mandi_price(commodity: str, market: str | None = None) -> dict:
    """Live wholesale mandi price (min/modal/max, INR per quintal) for a commodity,
    optionally at a specific market. Source: data.gov.in Agmarknet daily feed."""
    name = (commodity or "").strip()
    if not name:
        return {"error": "No commodity given."}
    # Agmarknet matches commodity/market names in Title-Case.
    params = {
        "api-key": config.DATA_GOV_IN_API_KEY,
        "format": "json",
        "limit": 50,
        "filters[commodity]": name.title(),
    }
    if market:
        params["filters[market]"] = market.strip().title()
    try:
        data = _get_json(config.AGMARKNET_URL, params)
    except requests.RequestException as e:
        return {"commodity": name, "error": f"Mandi price service unavailable: {e}"}

    records = data.get("records") or []
    # Fall back to an unfiltered lookup so a missing market doesn't dead-end the farmer.
    if not records and market:
        params.pop("filters[market]", None)
        try:
            records = (_get_json(config.AGMARKNET_URL, params).get("records") or [])
        except requests.RequestException as e:
            return {"commodity": name, "error": f"Mandi price service unavailable: {e}"}

    if not records:
        return {"commodity": name,
                "error": f"No mandi price reported today for '{name}'. Check the spelling "
                         "or try a major commodity (tomato, onion, wheat, paddy, cotton)."}

    top = records[0]
    markets_seen = {r.get("market") for r in records if r.get("market")}
    return {
        "commodity": top.get("commodity", name),
        "state": top.get("state"),
        "district": top.get("district"),
        "market": top.get("market"),
        "variety": top.get("variety"),
        "unit": "INR/quintal",
        "min": _to_num(top.get("min_price")),
        "modal": _to_num(top.get("modal_price")),
        "max": _to_num(top.get("max_price")),
        "arrival_date": top.get("arrival_date"),
        "other_markets_reporting": max(0, len(markets_seen) - 1),
    }


def _to_num(v):
    # Agmarknet returns prices as strings or ints depending on the row.
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return v


_CROP_ADVISORY = {
    "tomato": "Kharif tomato: watch for early blight in humid spells. Stake plants, "
              "drip-irrigate, and spray mancozeb only on confirmed lesions.",
    "wheat": "Rabi wheat: first irrigation at crown-root initiation (~21 days). "
             "Top-dress nitrogen after it. Scout for yellow rust in cool, damp weather.",
    "paddy": "Transplanted paddy: maintain 2-5 cm standing water through tillering. "
             "Apply nitrogen in three splits; monitor for stem borer at max tillering.",
    "cotton": "Bt cotton: install pheromone traps for pink bollworm at flowering. "
              "Avoid over-irrigation; potassium at boll development lifts fibre quality.",
}


def get_crop_advisory(crop: str, season: str | None = None) -> dict:
    """Curated agronomy advisory (stable best-practice reference, not a live feed)."""
    key = (crop or "").strip().lower()
    text = _CROP_ADVISORY.get(key)
    if not text:
        return {"crop": crop, "advisory": "No advisory for that crop in the reference set. "
                "Covered: tomato, wheat, paddy, cotton."}
    return {"crop": crop, "season": season or "current", "advisory": text,
            "source": "curated reference"}


_SCHEMES = {
    "pm-kisan": "PM-KISAN: Rs 6,000/year to landholding farmers in three Rs 2,000 "
                "instalments, paid directly to the Aadhaar-linked bank account.",
    "fasal bima": "PMFBY (crop insurance): premium 2% (kharif) / 1.5% (rabi) of sum "
                  "insured; covers yield loss from notified natural calamities.",
    "kcc": "Kisan Credit Card: short-term crop loans up to Rs 3 lakh at ~4% effective "
           "interest with timely repayment; also covers allied activities.",
    "soil health": "Soil Health Card: free soil testing every 2 years with crop-wise "
                   "nutrient and fertiliser recommendations.",
}

# Natural phrasings ("crop loan", "flood damage") mapped to each scheme key.
_SCHEME_ALIASES = {
    "pm-kisan": ["pm kisan", "pm-kisan", "pmkisan", "income support", "6000", "kisan samman"],
    "fasal bima": ["fasal bima", "pmfby", "insurance", "insure", "flood", "drought", "crop damage", "calamity"],
    "kcc": ["kcc", "kisan credit", "credit card", "crop loan", "short term loan", "loan"],
    "soil health": ["soil health", "soil card", "soil testing", "soil test", "fertiliser", "fertilizer", "nutrient"],
}


def get_govt_scheme(query: str) -> dict:
    """Curated lookup of Indian agriculture schemes (stable reference facts)."""
    q = " ".join((query or "").strip().lower().replace("-", " ").split())
    for key, aliases in _SCHEME_ALIASES.items():
        if any(alias in q for alias in aliases):
            return {"scheme": key, "details": _SCHEMES[key], "source": "curated reference"}
    return {"query": query, "details": "No matching scheme in the reference set. Try "
            "'PM-Kisan', 'Fasal Bima', 'KCC', or 'Soil Health'."}


# Single registry backing both the agent loop and the MCP server.
REGISTRY = {
    "get_weather": {
        "fn": get_weather,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the local 3-day weather outlook for a place, with spraying/irrigation advice.",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string", "description": "Village, town, or district name"}},
                    "required": ["location"],
                },
            },
        },
    },
    "get_mandi_price": {
        "fn": get_mandi_price,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_mandi_price",
                "description": "Get today's wholesale mandi price (min/modal/max, INR per quintal) for a commodity, optionally at a specific market.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commodity": {"type": "string", "description": "e.g. tomato, onion, wheat, paddy, cotton"},
                        "market": {"type": "string", "description": "Optional mandi/market name"},
                    },
                    "required": ["commodity"],
                },
            },
        },
    },
    "get_crop_advisory": {
        "fn": get_crop_advisory,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_crop_advisory",
                "description": "Get agronomy advice (pests, irrigation, nutrients) for a crop this season.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "crop": {"type": "string", "description": "e.g. tomato, wheat, paddy, cotton"},
                        "season": {"type": "string", "description": "Optional: kharif or rabi"},
                    },
                    "required": ["crop"],
                },
            },
        },
    },
    "get_govt_scheme": {
        "fn": get_govt_scheme,
        "schema": {
            "type": "function",
            "function": {
                "name": "get_govt_scheme",
                "description": "Look up an Indian government agriculture scheme (PM-Kisan, Fasal Bima, KCC, Soil Health Card).",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Scheme name or what the farmer wants"}},
                    "required": ["query"],
                },
            },
        },
    },
}

TOOL_SCHEMAS = [entry["schema"] for entry in REGISTRY.values()]


def dispatch(name: str, arguments: dict) -> dict:
    """Call a tool by name with a dict of arguments. Guarded for the agent loop."""
    entry = REGISTRY.get(name)
    if not entry:
        return {"error": f"Unknown tool: {name}"}
    try:
        return entry["fn"](**arguments)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # never let a tool crash the agent loop
        return {"error": f"{name} failed: {e}"}
