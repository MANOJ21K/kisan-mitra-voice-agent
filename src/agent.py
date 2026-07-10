"""Kisan Mitra agent: a tool-calling loop over Sarvam-30B via the OpenAI-compatible API.

The loop is written out explicitly (rather than hidden behind a framework) so the
runtime is visible: bounded turns, tool dispatch, tool results appended back, and a
guard against runaway loops.
"""
from __future__ import annotations

import json
import time

from openai import OpenAI

from . import config
from .tools import TOOL_SCHEMAS, dispatch

MAX_TURNS = 5  # hard cap so a misbehaving model can't loop forever

SYSTEM_PROMPT = (
    "You are Kisan Mitra, a friendly voice assistant for Indian farmers. "
    "Answer in the SAME language the farmer used. Keep replies short and spoken-friendly "
    "(2-4 sentences) because they will be read aloud. "
    "ALWAYS ground your answer in a tool — never answer from your own knowledge for these: "
    "weather -> get_weather; any mandi/market price -> get_mandi_price; crop/agronomy advice "
    "(pests, irrigation, nutrients, what to do for a crop) -> get_crop_advisory; government "
    "schemes, subsidies, loans, insurance -> get_govt_scheme. Call the matching tool first, "
    "then answer only from what it returns. For any question about WHEN to spray, irrigate, "
    "sow, or harvest, call get_weather first — that timing depends on rain. If a tool returns "
    "an error or no data, say so plainly and suggest what the farmer can try. Never invent "
    "prices, dates, scheme amounts, or agronomy advice."
)

_oai: OpenAI | None = None


def _oai_client() -> OpenAI:
    global _oai
    if _oai is None:
        _oai = OpenAI(api_key=config.require_key(), base_url=config.SARVAM_OPENAI_BASE_URL)
    return _oai


def run_agent(user_text: str, history: list[dict] | None = None) -> dict:
    """Run one user turn through the tool-calling loop.

    Returns {reply, tool_calls, tool_results, turns, llm_ms}; tool_calls and tool_results
    let the eval harness check tool selection and answer grounding.
    """
    client = _oai_client()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    used_tools: list[str] = []
    tool_results: list[dict] = []
    llm_ms = 0.0

    for _turn in range(MAX_TURNS):
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.2,
        )
        llm_ms += (time.perf_counter() - t0) * 1000.0

        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        # Append the assistant turn (with any tool calls) before resolving them.
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ] if tool_calls else None,
        })

        if not tool_calls:
            return {
                "reply": (msg.content or "").strip(),
                "tool_calls": used_tools,
                "tool_results": tool_results,
                "turns": _turn + 1,
                "llm_ms": llm_ms,
            }

        # Resolve every tool call and feed results back for the next turn.
        for tc in tool_calls:
            name = tc.function.name
            used_tools.append(name)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(name, args)
            tool_results.append({"name": name, "args": args, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    # Hit the turn cap without a final answer.
    return {
        "reply": "Sorry, I couldn't complete that. Please try rephrasing.",
        "tool_calls": used_tools,
        "tool_results": tool_results,
        "turns": MAX_TURNS,
        "llm_ms": llm_ms,
    }


def run_agent_stream(user_text: str, history: list[dict] | None = None,
                     meta: dict | None = None):
    """Streaming variant of run_agent for the live chat UI.

    Resolves any tool calls first (non-streaming), then streams the final answer token by
    token. Yields incremental text chunks (str). When the stream finishes it fills `meta`
    (if provided) with tools_used, tool_results, and llm_ms so the caller can show the
    latency/tools caption.
    """
    client = _oai_client()
    meta = meta if meta is not None else {}
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    used_tools: list[str] = []
    tool_results: list[dict] = []
    llm_ms = 0.0

    # Phase A: resolve tool calls (non-streaming) until the model is ready to answer.
    for _turn in range(MAX_TURNS):
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=config.CHAT_MODEL, messages=messages,
            tools=TOOL_SCHEMAS, tool_choice="auto", temperature=0.2,
        )
        llm_ms += (time.perf_counter() - t0) * 1000.0
        tool_calls = resp.choices[0].message.tool_calls or []
        if not tool_calls:
            break
        messages.append({
            "role": "assistant", "content": resp.choices[0].message.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            name = tc.function.name
            used_tools.append(name)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = dispatch(name, args)
            tool_results.append({"name": name, "args": args, "result": result})
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })

    # Phase B: stream the final answer. tool_choice="none" forces a text answer from the
    # tool results already in the message list; fall back to dropping tools if a provider
    # rejects that value.
    t0 = time.perf_counter()
    try:
        stream = client.chat.completions.create(
            model=config.CHAT_MODEL, messages=messages,
            tools=TOOL_SCHEMAS, tool_choice="none", temperature=0.2, stream=True,
        )
    except Exception:
        stream = client.chat.completions.create(
            model=config.CHAT_MODEL, messages=messages, temperature=0.2, stream=True,
        )
    for chunk in stream:
        choices = getattr(chunk, "choices", None)
        if not choices:
            continue
        delta = getattr(choices[0].delta, "content", None)
        if delta:
            yield delta
    llm_ms += (time.perf_counter() - t0) * 1000.0

    meta["tools_used"] = used_tools
    meta["tool_results"] = tool_results
    meta["llm_ms"] = llm_ms


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "Aaj Kolar mandi mein tamatar ka bhaav kya hai?"
    out = run_agent(q)
    print("Q:", q)
    print("Tools:", out["tool_calls"])
    print("A:", out["reply"])
    print(f"LLM latency: {out['llm_ms']:.0f} ms over {out['turns']} turn(s)")
