# Architecture

Kisan Mitra is a single-turn (optionally multi-turn) voice agent. One spoken question
flows through three Sarvam models and a bounded tool-calling loop, and comes back as
speech — with latency measured at every hop. Two of the four tools call live public
data sources; the other two serve curated reference data.

```mermaid
flowchart LR
    U([Farmer speaks<br/>Hindi / Kannada / ...]) -->|audio| STT

    subgraph Sarvam stack
      STT[Saaras v3<br/>speech-to-text]
      LLM[Sarvam-30B<br/>reasoning + tool calls]
      TTS[Bulbul v3<br/>text-to-speech]
    end

    STT -->|transcript| AGENT
    subgraph Agent runtime  (src/agent.py)
      AGENT{tool-calling loop<br/>max 5 turns}
      AGENT -->|tool call| TOOLS[(tools.py)]
      TOOLS -->|result| AGENT
    end
    AGENT -->|reply text| TTS
    TTS -->|audio| U

    TOOLS -->|get_weather| OM([Open-Meteo<br/>live forecast])
    TOOLS -->|get_mandi_price| AG([data.gov.in<br/>Agmarknet live])
    TOOLS -.->|advisory / schemes| REF([curated reference])

    TOOLS -.->|same registry| MCP[[MCP server<br/>mcp_server/server.py]]
    MCP -.-> EXT([Claude Desktop /<br/>Cursor / any MCP client])

    STT & LLM & TTS -->|per-stage ms| EVAL[[Eval harness<br/>eval/run_eval.py]]
    EVAL -->|grades replies| JUDGE([sarvam-105b<br/>LLM-as-judge])
```

## The pieces

| Layer | File | Responsibility |
|---|---|---|
| Speech in | `src/sarvam_client.py` → `transcribe` | Saaras v3, auto-detects Indian language, returns text + ms |
| Reasoning | `src/agent.py` → `run_agent` | Sarvam-30B tool-calling loop, bounded turns, guarded dispatch |
| Tools | `src/tools.py` | 4 farmer tools + JSON schemas; one registry shared with MCP |
| Speech out | `src/sarvam_client.py` → `synthesize` | Bulbul v3, decodes base64 audio + ms |
| Orchestration | `src/pipeline.py` | wires the three stages, captures asr/llm/tts/total ms |
| UI | `streamlit_app.py` | Streamlit streaming multi-turn voice chat (mic + text) |
| MCP | `mcp_server/server.py` | exposes the same tools to external MCP clients |
| Eval | `eval/` | WER, tool accuracy, answer keywords, latency p50/p95, LLM-as-judge |

## Data sources

| Tool | Source | Live? |
|---|---|---|
| `get_weather` | Open-Meteo geocoding + forecast (keyless) | live |
| `get_mandi_price` | data.gov.in Agmarknet daily mandi feed (free key) | live |
| `get_crop_advisory` | curated agronomy best-practice | reference |
| `get_govt_scheme` | curated scheme facts (PM-Kisan, PMFBY, KCC, Soil Health) | reference |

## Design choices

- **Explicit tool loop, not a framework.** The runtime (bounded turns, tool dispatch,
  results fed back, loop guard) is written out in `agent.py` so its failure modes are
  visible and controllable, rather than hidden behind a framework abstraction.
- **One tool registry, two consumers.** `tools.py` backs both the in-process agent and
  the MCP server, so there's no drift between what the agent can do and what an external
  client sees.
- **Tools never raise.** Every tool returns a dict, `{"error": ...}` on failure, so a
  flaky upstream API degrades gracefully into an honest spoken reply instead of a crash.
- **Latency is a first-class output.** Every stage returns `(result, ms)`; the UI shows
  it and the eval harness aggregates p50/p95 — because a voice agent lives or dies on it.
- **Evals from day one, and Sarvam-native.** `eval/metrics.py` is key-free and
  self-testing; `run_eval.py` scores tool selection, grounded answers, and latency; a
  stronger Sarvam model (sarvam-105b) acts as LLM-as-judge on faithfulness and
  spoken-friendliness (`eval/judge.py`).
