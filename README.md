# 🌾 Kisan Mitra — a multilingual voice agent on Sarvam's stack

A spoken farmer-advisory assistant built end-to-end on **Sarvam AI**'s own models:

> **Saaras v3** (speech-to-text) → **Sarvam-30B** (reasoning + tool-calling) → **Bulbul v3** (text-to-speech)

Ask — by voice, in Hindi / Kannada / Tamil / … — about **mandi prices, weather,
crop advice, or government schemes**, and get a spoken reply in the same language.
It ships with an **MCP server** exposing the same tools and an **eval harness** that
scores tool selection, answer accuracy, and latency (p50/p95).

<!-- Add after deploy:  🔗 Live demo: https://huggingface.co/spaces/<you>/kisan-mitra  ·  📹 90-sec walkthrough: <link> -->

---

## Why this project

Built as targeted proof-of-work for Sarvam AI's **Applied AI Engineer** and **Forward
Deployed Engineer** roles. It deliberately exercises every capability those JDs ask for:

| JD asks for | Where it lives here |
|---|---|
| Deploy conversational agents across voice channels | full ASR→LLM→TTS voice loop (`app.py`, `src/pipeline.py`) |
| Build MCP servers | `mcp/server.py` sharing one tool registry with the agent |
| Agent runtime: state, retries, tool-calling, guardrails | explicit bounded loop in `src/agent.py` |
| RAG / tool-calling / structured tools | JSON-schema tools + guarded dispatch in `src/tools.py` |
| Streaming, cost & latency engineering | per-stage latency captured everywhere, shown in UI + eval |
| Evaluation pipelines for AI systems | `eval/` — WER, tool accuracy, answer accuracy, p50/p95 |
| Familiarity with Sarvam's own APIs | built directly on Saaras / Sarvam-30B / Bulbul / Translate |

Architecture diagram and design rationale: [docs/architecture.md](docs/architecture.md).

---

## Quickstart

```bash
git clone <this-repo> && cd kisan-mitra-voice-agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then paste your key from dashboard.sarvam.ai
```

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
python mcp/server.py          # stdio; mount from Claude Desktop / Cursor / any MCP client
```

### Run the evals
```bash
python eval/metrics.py        # key-free self-test of WER + percentile maths
python eval/run_eval.py       # full run over the golden set (needs SARVAM_API_KEY)
python eval/run_eval.py --speak --n 5   # include TTS latency, first 5 cases
```

Sample eval output:
```
tool accuracy   : 9/10  (90%)
answer accuracy : 8/10  (80%)
LLM latency     : p50 620 ms · p95 1180 ms · max 1400 ms
total latency   : p50 640 ms · p95 1200 ms
```
*(illustrative — real numbers depend on your key, region, and network)*

---

## Layout

```
kisan-mitra-voice-agent/
├── app.py                 # Gradio voice UI — HF Spaces entry point
├── src/
│   ├── config.py          # key, base URLs, model ids, languages
│   ├── sarvam_client.py   # Saaras STT · Bulbul TTS · Translate (each returns latency)
│   ├── tools.py           # 4 farmer tools + schemas + dispatch (one registry)
│   ├── agent.py           # Sarvam-30B tool-calling loop (the agent runtime)
│   └── pipeline.py        # audio→STT→agent→TTS, per-stage timing
├── mcp/server.py          # MCP server exposing the same tools
├── eval/
│   ├── metrics.py         # WER + latency percentiles (key-free, self-testing)
│   ├── run_eval.py        # golden-set runner
│   └── golden_set.jsonl   # 10 labelled test cases
└── docs/architecture.md   # diagram + design rationale
```

---

## Notes on data honesty

The **speech, language understanding, and agent stack are live Sarvam APIs.** The tool
*data* (mandi prices, weather, scheme amounts) is representative **mock data** — each
tool in `src/tools.py` marks the real source to wire in (Agmarknet / data.gov.in for
prices, Open-Meteo / IMD for weather, PM-Kisan / MyScheme for schemes). Schemas stay the
same; only the function bodies change.

## Deploy to Hugging Face Spaces

1. Create a **Gradio** Space, push this repo.
2. Add `SARVAM_API_KEY` as a Space **secret**.
3. Spaces runs `app.py` automatically. Drop the live URL + a short demo video at the top
   of this README and in the LinkedIn post.
