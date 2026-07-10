# Kisan Mitra 🌾

A multilingual, voice-first advisory assistant for Indian farmers, built end-to-end on Sarvam AI's stack.

[![Live demo](https://img.shields.io/badge/demo-live-brightgreen.svg)](https://kisan-mitra-voice-agent.onrender.com/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Built on Sarvam AI](https://img.shields.io/badge/built%20on-Sarvam%20AI-orange.svg)](https://sarvam.ai)

**🔗 Live demo:** https://kisan-mitra-voice-agent.onrender.com/
*(free tier — the first request after idle takes ~50s to wake the server)*

A farmer speaks a question in their own language — Hindi, Kannada, Tamil, and more — and
hears a spoken answer back in the same language. Under the hood, one Sarvam pipeline
handles the whole loop:

```
Saaras v3 (speech-to-text) → Sarvam-30B (reasoning + tool-calling) → Bulbul v3 (text-to-speech)
```

The assistant answers questions about **mandi (market) prices, weather, crop advice, and
government schemes** — grounding each answer in a tool call rather than guessing. Weather
and prices come from live public APIs; the whole thing runs on Sarvam's own models so
Indian-language speech, reasoning, and speech synthesis stay in a single stack.

## Features

- **Streaming multi-turn chat** — a Streamlit conversation where the reply streams token by token (single-pass: tools resolve inline, then the answer streams) and the voiceover autoplays.
- **Full voice loop** — speech in, speech out, in the farmer's own language (7 languages).
- **Grounded tool-calling agent** — an explicit, bounded loop over Sarvam-30B that calls tools instead of hallucinating prices or dates.
- **Live data** — real weather (Open-Meteo) and real mandi prices (data.gov.in Agmarknet), with graceful `{error: ...}` fallback when an upstream API is down.
- **MCP server** — the same four tools exposed over the Model Context Protocol for any MCP client (Claude Desktop, Cursor, custom agents).
- **Evaluation harness** — tool-selection accuracy, grounded-answer keywords, WER, latency p50/p95, and an **LLM-as-judge on sarvam-105b** scoring faithfulness and spoken-friendliness.
- **Latency as a first-class metric** — every stage is timed and surfaced in both the UI and the eval report.
- **Tested** — 39 unit tests (network and LLM fully mocked, key-free), lint-clean via ruff.

## Prerequisites

- Python 3.11 or newer
- A **Sarvam AI API key** — free tier at [dashboard.sarvam.ai](https://dashboard.sarvam.ai) (required for speech, LLM, and TTS)
- *(Optional)* a free **data.gov.in API key** for reliable live mandi prices — the app ships with a public sample key that works but is rate-limited

## Installation

```bash
git clone https://github.com/MANOJ21K/kisan-mitra-voice-agent
cd kisan-mitra-voice-agent

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # then add your SARVAM_API_KEY
```

`.env` keys:

| Variable | Required | Purpose |
|---|---|---|
| `SARVAM_API_KEY` | yes | Saaras STT, Sarvam-30B, Bulbul TTS |
| `DATA_GOV_IN_API_KEY` | no | live mandi prices (falls back to a rate-limited sample key) |

## Usage

### Run the voice app

```bash
streamlit run streamlit_app.py
```

Opens a **Streamlit chat**: speak or type in a single multi-turn conversation. The reply
**streams in token by token**, the **Bulbul voiceover autoplays** when the text finishes,
and each turn shows which tools fired plus per-stage latency.

### Query the agent from the CLI

```bash
python -m src.agent "Aaj Kolar mandi mein tamatar ka bhaav kya hai?"
```

```
Q: Aaj Kolar mandi mein tamatar ka bhaav kya hai?
Tools: ['get_mandi_price']
A: Kolar mandi mein aaj tamatar ka modal bhaav 1200 rupaye prati quintal hai …
LLM latency: 1768 ms over 2 turn(s)
```

### Run the MCP server

```bash
python mcp_server/server.py    # stdio transport
```

<details>
<summary>Claude Desktop config</summary>

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

### Run the evaluation harness

```bash
python eval/metrics.py                  # key-free self-test of WER + percentile maths
python eval/run_eval.py                 # tool + answer accuracy + latency (needs SARVAM_API_KEY)
python eval/run_eval.py --judge --n 5   # add sarvam-105b LLM-as-judge, first 5 cases
python eval/run_eval.py --speak         # also measure TTS latency
```

```
Kisan Mitra eval — 12 cases
tool accuracy        : 11/12  (92%)
answer accuracy      : 10/12  (83%)
judge faithfulness   : mean 4.6/5 · min 3/5  (sarvam-105b)
judge spoken-friendly: mean 4.8/5 · min 4/5
LLM latency          : p50 620 ms · p95 1180 ms · max 1400 ms
```
*(illustrative — real numbers depend on your key, region, and network)*

## Data sources

| Tool | Source | Live? |
|---|---|---|
| `get_weather` | [Open-Meteo](https://open-meteo.com) geocoding + forecast (keyless) | live |
| `get_mandi_price` | [data.gov.in Agmarknet](https://data.gov.in) daily mandi feed (free key) | live |
| `get_crop_advisory` | curated agronomy best-practice | reference |
| `get_govt_scheme` | curated scheme facts (PM-Kisan, PMFBY, KCC, Soil Health) | reference |

The speech and agent stack are live Sarvam APIs. Weather and mandi prices are live
third-party feeds — if an upstream API is unreachable the tool returns a clear error the
assistant relays honestly, never an invented price. Crop advisory and scheme details are
curated reference data (stable facts, labelled as such in the tool output), not a live feed.

## Testing

```bash
pip install ruff pytest
ruff check .            # lint
python eval/metrics.py  # key-free metrics self-test
pytest -q               # 39 tests — network and LLM mocked, no API key needed
```

The suite is network-free and key-free (mocked APIs and LLM), so it runs anywhere without credentials.

## Project structure

```
kisan-mitra-voice-agent/
├── streamlit_app.py       # Streamlit voice chat — app entry point
├── src/
│   ├── config.py          # keys, base URLs, model ids, languages, data-source config
│   ├── sarvam_client.py   # Saaras STT · Bulbul TTS · Translate (each returns latency)
│   ├── tools.py           # 4 farmer tools + schemas + dispatch (single registry)
│   ├── agent.py           # Sarvam-30B tool-calling loop (the agent runtime)
│   └── pipeline.py        # audio → STT → agent → TTS, per-stage timing
├── mcp_server/server.py   # MCP server exposing the same tools
├── eval/
│   ├── metrics.py         # WER + latency percentiles (key-free, self-testing)
│   ├── judge.py           # LLM-as-judge on sarvam-105b
│   ├── run_eval.py        # golden-set runner (--judge, --speak, --n)
│   └── golden_set.jsonl   # 12 labelled test cases (incl. edge cases)
├── tests/                 # 39 pytest tests — mocked network + LLM, no key
├── docs/architecture.md   # diagram + design rationale
├── CLAUDE.md              # conventions for contributors and AI agents
├── Dockerfile
└── render.yaml            # one-click Render deploy blueprint
```

See [docs/architecture.md](docs/architecture.md) for the full diagram and design rationale.

## Deployment

The live demo runs on Render's free tier, deployed from the `Dockerfile` via `render.yaml`.

### Render (one-click blueprint)

1. On [Render](https://render.com): **New +** → **Blueprint** → connect this repo.
2. Render reads `render.yaml` and provisions the `kisan-mitra` web service.
3. Set `SARVAM_API_KEY` (and optionally `DATA_GOV_IN_API_KEY`) as environment variables when prompted.
4. Apply — Render builds the Docker image and serves the app. The free plan sleeps after 15 min idle and cold-starts (~50s) on the next request.

**Keep-warm (kills the cold start):** point a free [UptimeRobot](https://uptimerobot.com) HTTP monitor at `https://<your-app>.onrender.com/_stcore/health` on a 5-minute interval so the instance never idles out. This is the single biggest latency win on the free tier.

### Docker

```bash
docker build -t kisan-mitra .
docker run -p 7860:7860 -e SARVAM_API_KEY=sk_your_key kisan-mitra
# open http://localhost:7860
```

## Contributing

Issues and pull requests are welcome. Before opening a PR, please run `ruff check .`,
`pytest -q`, and `python eval/metrics.py` — all three must pass. Contributor and
AI-agent conventions are documented in [CLAUDE.md](CLAUDE.md).

## Acknowledgments

- [Sarvam AI](https://sarvam.ai) — Saaras, Sarvam-30B, sarvam-105b, and Bulbul models
- [Open-Meteo](https://open-meteo.com) — free weather forecasts
- [data.gov.in](https://data.gov.in) — Agmarknet daily mandi price feed

## License

Released under the [MIT License](LICENSE).
