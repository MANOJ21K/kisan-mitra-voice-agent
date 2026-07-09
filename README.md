# 🌾 Kisan Mitra — a multilingual voice agent on Sarvam's stack

[![CI](https://github.com/MANOJ21K/kisan-mitra-voice-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MANOJ21K/kisan-mitra-voice-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Built on Sarvam AI](https://img.shields.io/badge/built%20on-Sarvam%20AI-orange.svg)](https://sarvam.ai)

A spoken farmer-advisory assistant built end-to-end on **Sarvam AI**'s own models:

> **Saaras v3** (speech-to-text) → **Sarvam-30B** (reasoning + tool-calling) → **Bulbul v3** (text-to-speech)

Ask — by voice, in Hindi / Kannada / Tamil / … — about **mandi prices, weather,
crop advice, or government schemes**, and get a spoken reply in the same language.
Weather and mandi prices come from **live public APIs**. It ships with an **MCP server**
exposing the same tools and an **eval harness** — including an **LLM-as-judge on
sarvam-105b** — that scores tool selection, answer faithfulness, and latency (p50/p95).

<!-- Add after deploy:  🔗 Live demo: https://huggingface.co/spaces/<you>/kisan-mitra  ·  📹 90-sec walkthrough: <link> -->

---

## Why voice, and why this stack

Most Indian farmers can't easily use a typed, English-first app: many are more
comfortable speaking their own language than reading, and the information they need —
today's mandi price, whether it's about to rain, what to do for a pest — is scattered
across portals they never open. A **voice-first assistant in the farmer's own language**
removes both barriers at once.

Doing that well needs three things done together: accurate Indian-language speech,
grounded tool-augmented reasoning, and low latency (a voice reply that lags feels broken).
Sarvam's models cover all three natively — **Saaras** for speech, **Sarvam-30B** for
tool-calling, **Bulbul** for natural TTS — so the whole loop stays in one stack instead of
being stitched across vendors with a language gap at every seam.

How the codebase is organised:

| Concern | Where it lives |
|---|---|
| End-to-end voice loop (ASR → LLM → TTS) | `app.py`, `src/pipeline.py` |
| Agent runtime — bounded turns, tool dispatch, guardrails | `src/agent.py` |
| Tools + JSON schemas + guarded dispatch (one registry) | `src/tools.py` |
| Same tools exposed to external clients | `mcp_server/server.py` |
| Real external data + graceful error handling | Open-Meteo, data.gov.in Agmarknet |
| Latency as a first-class output | per-stage `ms` captured everywhere, shown in UI + eval |
| Evaluation | `eval/` — WER, tool accuracy, answer keywords, LLM-as-judge, p50/p95 |

Architecture diagram and design rationale: [docs/architecture.md](docs/architecture.md).
Working conventions for contributors and AI agents: [CLAUDE.md](CLAUDE.md).

---

## Data sources

| Tool | Source | Live? |
|---|---|---|
| `get_weather` | [Open-Meteo](https://open-meteo.com) geocoding + forecast (keyless) | **live** |
| `get_mandi_price` | [data.gov.in Agmarknet](https://data.gov.in) daily mandi feed (free key) | **live** |
| `get_crop_advisory` | curated agronomy best-practice | reference |
| `get_govt_scheme` | curated scheme facts (PM-Kisan, PMFBY, KCC, Soil Health) | reference |

The **speech, language understanding, and agent stack are live Sarvam APIs.** Weather and
mandi prices are **live third-party feeds**; if an upstream API is unreachable the tool
returns a clear error the assistant relays honestly (it never invents a price). Crop
advisory and scheme details are **curated reference data** — stable facts, labelled as
such in the tool output — not a live feed.

---

## Quickstart

```bash
git clone https://github.com/MANOJ21K/kisan-mitra-voice-agent
cd kisan-mitra-voice-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your key from dashboard.sarvam.ai
```

**Keys.** `SARVAM_API_KEY` is required (speech + LLM + TTS). Live mandi prices use a
`DATA_GOV_IN_API_KEY` from [data.gov.in](https://data.gov.in) — optional: the app ships
with a public sample key that works but is heavily rate-limited, so register your own free
key for reliable prices. Weather needs no key.

### Run the voice app
```bash
python app.py                 # opens the Gradio UI (mic + text tabs)
```

### Try the agent from the CLI
```bash
python -m src.agent "Aaj Kolar mandi mein tamatar ka bhaav kya hai?"
```

### Run the MCP server
```bash
python mcp_server/server.py   # stdio; mount from Claude Desktop / Cursor / any MCP client
```

<details>
<summary>Claude Desktop MCP config snippet</summary>

```json
{
  "mcpServers": {
    "kisan-mitra": {
      "command": "python",
      "args": ["/absolute/path/to/kisan-mitra-voice-agent/mcp_server/server.py"]
    }
  }
}
```
</details>

### Run the evals
```bash
python eval/metrics.py                  # key-free self-test of WER + percentile maths
python eval/run_eval.py                 # full run over the golden set (needs SARVAM_API_KEY)
python eval/run_eval.py --judge --n 5   # add sarvam-105b LLM-as-judge, first 5 cases
python eval/run_eval.py --speak         # include TTS latency
```

Sample eval output:
```
tool accuracy        : 11/12  (92%)
answer accuracy      : 10/12  (83%)
judge faithfulness   : mean 4.6/5 · min 3/5  (sarvam-105b)
judge spoken-friendly: mean 4.8/5 · min 4/5
LLM latency          : p50 620 ms · p95 1180 ms · max 1400 ms
total latency        : p50 640 ms · p95 1200 ms
```
*(illustrative — real numbers depend on your key, region, and network)*

---

## Tests & CI

```bash
pip install ruff pytest
ruff check .        # lint
pytest -q           # 35 tests — all network-free and key-free (mocked APIs + LLM)
```

Every push and PR runs **ruff + the metrics self-test + pytest** on Python 3.11 and 3.12
via [GitHub Actions](.github/workflows/ci.yml). Tests mock the network and the Sarvam
client, so CI needs no API key.

---

## Layout

```
kisan-mitra-voice-agent/
├── app.py                 # Gradio voice UI — HF Spaces entry point
├── src/
│   ├── config.py          # key, base URLs, model ids, languages, data-source config
│   ├── sarvam_client.py   # Saaras STT · Bulbul TTS · Translate (each returns latency)
│   ├── tools.py           # 4 farmer tools + schemas + dispatch (one registry)
│   ├── agent.py           # Sarvam-30B tool-calling loop (the agent runtime)
│   └── pipeline.py        # audio→STT→agent→TTS, per-stage timing
├── mcp_server/server.py   # MCP server exposing the same tools
├── eval/
│   ├── metrics.py         # WER + latency percentiles (key-free, self-testing)
│   ├── judge.py           # LLM-as-judge on sarvam-105b (faithfulness + spoken-friendliness)
│   ├── run_eval.py        # golden-set runner (--judge, --speak, --n)
│   └── golden_set.jsonl   # 12 labelled test cases (incl. edge cases)
├── tests/                 # 35 pytest tests — mocked network + LLM, no key
├── docs/architecture.md   # diagram + design rationale
├── CLAUDE.md              # conventions for AI agents / contributors
├── Dockerfile             # container image for the Gradio app
└── .github/workflows/ci.yml
```

---

## Deploy

### Hugging Face Spaces
1. Create a **Gradio** Space, push this repo.
2. Add `SARVAM_API_KEY` (and optionally `DATA_GOV_IN_API_KEY`) as Space **secrets**.
3. Spaces runs `app.py` automatically. Drop the live URL + a short demo video at the top
   of this README and in the LinkedIn post.

### Docker
```bash
docker build -t kisan-mitra .
docker run -p 7860:7860 -e SARVAM_API_KEY=sk_your_key kisan-mitra
# open http://localhost:7860
```
