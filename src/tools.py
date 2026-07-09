"""Farmer-advisory tools for the Kisan Mitra agent.

Each tool is a plain Python function plus an OpenAI-style JSON schema. The same
registry backs both the live agent loop (src/agent.py) and the MCP server
(mcp/server.py), so there is exactly one source of truth for the tools.

The data here is representative mock data. Wiring points to real sources are noted
inline (Agmarknet / data.gov.in for mandi prices, IMD or Open-Meteo for weather,
the PM-Kisan / MyScheme registries for schemes) — swap the bodies, keep the schemas.
"""
from __future__ import annotations

import datetime as _dt

# --- mock data stores (stand-ins for external services) --------------------

_MANDI_PRICES = {
    # commodity -> {market: (min, modal, max) INR per quintal}
    "tomato": {"Kolar": (800, 1200, 1600), "Bengaluru": (1000, 1450, 1900)},
    "onion": {"Kolar": (1400, 1800, 2200), "Bengaluru": (1600, 2000, 2500)},
    "wheat": {"Indore": (2200, 2450, 2700), "Delhi": (2300, 2550, 2800)},
    "paddy": {"Karnal": (2000, 2203, 2400), "Raichur": (1900, 2100, 2350)},
    "cotton": {"Guntur": (6800, 7200, 7600), "Yavatmal": (6900, 7350, 7800)},
}

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


# --- tool implementations --------------------------------------------------

def get_weather(location: str) -> dict:
    """Mock 3-day outlook. Replace with Open-Meteo / IMD gridded forecast."""
    return {
        "location": location,
        "as_of": _dt.date.today().isoformat(),
        "forecast": [
            {"day": "today", "high_c": 31, "low_c": 22, "rain_mm": 4, "summary": "Partly cloudy, light showers by evening"},
            {"day": "tomorrow", "high_c": 30, "low_c": 21, "rain_mm": 12, "summary": "Scattered thundershowers"},
            {"day": "day_after", "high_c": 32, "low_c": 23, "rain_mm": 0, "summary": "Clear and dry"},
        ],
        "advice": "Hold off on spraying today/tomorrow — rain will wash it off. Spray on the dry day.",
    }


def get_mandi_price(commodity: str, market: str | None = None) -> dict:
    """Mock mandi (wholesale) prices. Replace with Agmarknet / data.gov.in API."""
    key = commodity.strip().lower()
    markets = _MANDI_PRICES.get(key)
    if not markets:
        return {"commodity": commodity, "error": "No price data for that commodity in the demo dataset."}
    if market:
        row = markets.get(market) or next(iter(markets.values()))
        chosen = market if market in markets else next(iter(markets))
    else:
        chosen, row = next(iter(markets.items()))
    return {
        "commodity": commodity, "market": chosen, "unit": "INR/quintal",
        "min": row[0], "modal": row[1], "max": row[2],
        "date": _dt.date.today().isoformat(),
    }


def get_crop_advisory(crop: str, season: str | None = None) -> dict:
    """Mock agronomy advisory. Replace with ICAR / state agri-university feeds."""
    key = crop.strip().lower()
    text = _CROP_ADVISORY.get(key)
    if not text:
        return {"crop": crop, "advisory": "No advisory for that crop in the demo dataset."}
    return {"crop": crop, "season": season or "current", "advisory": text}


# Common ways a farmer phrases each scheme -> scheme key. Keeps the mock lookup
# robust to natural queries ("crop loan", "flood damage") the way a real intent
# layer would; the real registry lookup would replace this outright.
_SCHEME_ALIASES = {
    "pm-kisan": ["pm kisan", "pm-kisan", "pmkisan", "income support", "6000", "kisan samman"],
    "fasal bima": ["fasal bima", "pmfby", "insurance", "insure", "flood", "drought", "crop damage", "calamity"],
    "kcc": ["kcc", "kisan credit", "credit card", "crop loan", "short term loan", "loan"],
    "soil health": ["soil health", "soil card", "soil testing", "soil test", "fertiliser", "fertilizer", "nutrient"],
}


def get_govt_scheme(query: str) -> dict:
    """Mock scheme lookup. Replace with the MyScheme / PM-Kisan registries."""
    q = " ".join(query.strip().lower().replace("-", " ").split())
    for key, aliases in _SCHEME_ALIASES.items():
        if any(alias in q for alias in aliases):
            return {"scheme": key, "details": _SCHEMES[key]}
    return {"query": query, "details": "No matching scheme in the demo dataset. Try 'PM-Kisan', 'Fasal Bima', 'KCC', or 'Soil Health'."}


# --- registry: schemas + dispatch (one source of truth) --------------------

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
