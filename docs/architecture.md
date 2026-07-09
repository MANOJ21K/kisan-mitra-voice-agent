# Architecture

Kisan Mitra is a single-turn (optionally multi-turn) voice agent. One spoken question
flows through three Sarvam models and a bounded tool-calling loop, and comes back as
speech — with latency measured at every hop.

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

    TOOLS -.->|same registry| MCP[[MCP server<br/>mcp/server.py]]
    MCP -.-> EXT([Claude Desktop /<br/>Cursor / any MCP client])

    STT & LLM & TTS -->|per-stage ms| EVAL[[Eval harness<br/>eval/run_eval.py<br/>WER · tool acc · p50/p95]]
```

## The pieces

| Layer | File | Responsibility |
|---|---|---|
| Speech in | `src/sarvam_client.py` → `transcribe` | Saaras v3, auto-detects Indian language, returns text + ms |
| Reasoning | `src/agent.py` → `run_agent` | Sarvam-30B tool-calling loop, bounded turns, guarded dispatch |
| Tools | `src/tools.py` | 4 farmer tools + JSON schemas; one registry shared with MCP |
| Speech out | `src/sarvam_client.py` → `synthesize` | Bulbul v3, decodes base64 audio + ms |
| Orchestration | `src/pipeline.py` | wires the three stages, captures asr/llm/tts/total ms |
| UI | `app.py` | Gradio mic + text tabs; HF Spaces entry point |
| MCP | `mcp/server.py` | exposes the same tools to external MCP clients |
| Eval | `eval/` | WER, tool accuracy, answer accuracy, latency p50/p95 |

## Design choices worth defending in an interview

- **Explicit tool loop, not a framework.** The runtime (bounded turns, tool dispatch,
  results fed back, loop guard) is written out in `agent.py` so its failure modes are
  visible and controllable — the "agent runtime" the Applied AI JD asks about.
- **One tool registry, two consumers.** `tools.py` backs both the in-process agent and
  the MCP server, so there's no drift between what the agent can do and what an external
  client sees.
- **Latency is a first-class output.** Every stage returns `(result, ms)`; the UI shows
  it and the eval harness aggregates p50/p95 — because a voice agent lives or dies on it.
- **Evals from day one.** `eval/metrics.py` is key-free and self-testing; `run_eval.py`
  scores tool selection, grounded-answer accuracy, and latency over a golden set.
```
