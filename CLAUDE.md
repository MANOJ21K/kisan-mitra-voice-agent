# CLAUDE.md

Guidance for AI coding agents (and humans) working in this repo.

## What this is

**Kisan Mitra** — a multilingual voice assistant for Indian farmers, built end-to-end on
Sarvam AI's stack:

```
Saaras v3 (STT)  ->  Sarvam-30B (reasoning + tool-calling)  ->  Bulbul v3 (TTS)
```

A farmer asks — by voice, in Hindi/Kannada/Tamil/… — about mandi prices, weather, crop
advice, or government schemes, and gets a spoken reply in the same language. The repo also
ships an MCP server exposing the same tools and an eval harness (including an
LLM-as-judge on sarvam-105b).

## Architecture (one-minute map)

| Layer | File | Note |
|---|---|---|
| Speech in/out | `src/sarvam_client.py` | Saaras STT, Bulbul TTS, Translate — each returns `(result, ms)` |
| Agent runtime | `src/agent.py` | explicit bounded tool-calling loop over Sarvam-30B (OpenAI-compatible endpoint) |
| Tools | `src/tools.py` | **single registry** (`REGISTRY`) → schemas + dispatch |
| Orchestration | `src/pipeline.py` | audio → STT → agent → TTS, per-stage timing (used by eval) |
| Streaming | `src/agent.py::run_agent_stream` | single-pass streaming for the chat UI; yields `(kind, text)` events |
| UI | `streamlit_app.py` | Streamlit multi-turn voice chat; app entry point |
| MCP | `mcp_server/server.py` | exposes the same `src/tools.py` functions to any MCP client |
| Eval | `eval/` | `metrics.py` (WER + percentiles, key-free), `run_eval.py`, `judge.py` |

**The one invariant that matters:** `src/tools.py` is the single source of truth for tools.
Both the in-process agent and the MCP server import from it — never duplicate a tool.

## Commands

```bash
# setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # + `pip install ruff pytest` for dev
cp .env.example .env                    # add SARVAM_API_KEY (see below)

# run
streamlit run streamlit_app.py          # Streamlit voice chat UI
python -m src.agent "Aaj tamatar ka bhaav?"   # agent from CLI
python mcp_server/server.py             # MCP server (stdio)

# quality gates (run before every commit)
python eval/metrics.py                  # key-free self-test — MUST pass
pytest -q                               # 39 tests, no network, no key — MUST pass
ruff check .                            # lint — MUST pass

# eval (needs SARVAM_API_KEY)
python eval/run_eval.py --n 3           # tool + keyword accuracy + latency
python eval/run_eval.py --judge         # add sarvam-105b LLM-as-judge scores
```

## Conventions

- **Every Sarvam API call returns `(result, elapsed_ms)`** (`src/sarvam_client.py`). Keep
  latency a first-class output — the UI and eval both depend on it.
- **Tools never raise.** On any failure a tool returns `{"error": ...}`; the agent's system
  prompt tells the model to relay that plainly. `dispatch()` in `src/tools.py` is the guard.
- **All `requests` calls carry a timeout** (`config.HTTP_TIMEOUT_S`). No unbounded network.
- **Model IDs live in `src/config.py`**, overridable by env. Don't hardcode them elsewhere.

## Data honesty (do not regress)

- `get_weather` → **live** Open-Meteo (keyless). `get_mandi_price` → **live** data.gov.in
  Agmarknet (free key). These are real feeds.
- `get_crop_advisory` / `get_govt_scheme` → **curated static reference data** (stable
  agronomy/scheme facts), labelled `"source": "curated reference"`. Never describe this
  curated data as a live feed in docs or replies.

## Rules for agents

- **Never commit `.env`** (holds a real key) or `myenv/`/`.venv/`. Both are gitignored — keep it that way.
- Before committing non-trivial changes: `ruff check .`, `pytest -q`, and `python eval/metrics.py` must all pass.
- Tests must stay **network-free and key-free** (mock `requests` and the LLM client). CI runs with `SARVAM_API_KEY=""`.
- If you add or change a tool, update its schema in the same `REGISTRY` entry and add a test in `tests/test_tools.py`.
