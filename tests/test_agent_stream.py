"""Tests for run_agent_stream with a fully mocked streaming client — no network, no key.

Covers the single-pass streaming path (direct answer + tool-call round trip) and the
fallback to non-streaming run_agent when streaming fails.
"""
from __future__ import annotations

from types import SimpleNamespace

from src import agent


def _chunk(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(content=content, tool_calls=tool_calls))])


def _tc(index, tc_id, name, args):
    return SimpleNamespace(index=index, id=tc_id,
                           function=SimpleNamespace(name=name, arguments=args))


class FakeStreamClient:
    """Each create() call returns the next scripted list of stream chunks."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0
        outer = self

        class _Completions:
            def create(self, **kwargs):
                i = min(outer.calls, len(outer._scripted) - 1)
                outer.calls += 1
                return iter(outer._scripted[i])

        self.chat = SimpleNamespace(completions=_Completions())


def test_stream_direct_answer(monkeypatch):
    script = [[_chunk("Namaste"), _chunk(", "), _chunk("kisan.")]]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeStreamClient(script))
    meta = {}
    events = list(agent.run_agent_stream("hi", [], meta))
    assert "".join(t for k, t in events if k == "token") == "Namaste, kisan."
    assert all(k == "token" for k, _ in events)     # no tools -> no status events
    assert meta["tools_used"] == []
    assert meta["tool_results"] == []


def test_stream_tool_round_trip(monkeypatch):
    call1 = [_chunk(tool_calls=[_tc(0, "c1", "get_crop_advisory", '{"crop": "wheat"}')])]
    call2 = [_chunk("Sow wheat "), _chunk("and irrigate at day 21.")]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeStreamClient([call1, call2]))
    meta = {}
    events = list(agent.run_agent_stream("wheat advice?", [], meta))
    kinds = [k for k, _ in events]
    assert "status" in kinds                         # tool activity surfaced
    assert "irrigate" in "".join(t for k, t in events if k == "token")
    assert meta["tools_used"] == ["get_crop_advisory"]
    assert meta["tool_results"][0]["name"] == "get_crop_advisory"
    assert "nitrogen" in meta["tool_results"][0]["result"]["advisory"].lower()


def test_stream_tool_args_split_across_chunks(monkeypatch):
    # Real APIs split tool-call arguments over several deltas; accumulation must handle it.
    call1 = [
        _chunk(tool_calls=[_tc(0, "c1", "get_crop_advisory", '{"cr')]),
        _chunk(tool_calls=[_tc(0, None, "", 'op": "wheat"}')]),
    ]
    call2 = [_chunk("Wheat advice here.")]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeStreamClient([call1, call2]))
    meta = {}
    list(agent.run_agent_stream("wheat?", [], meta))
    assert meta["tool_results"][0]["args"] == {"crop": "wheat"}


class FakeFallbackClient:
    """Streaming create() raises; non-streaming create() returns a final answer."""
    def __init__(self, content):
        class _Completions:
            def create(self, **kwargs):
                if kwargs.get("stream"):
                    raise RuntimeError("streaming unsupported")
                msg = SimpleNamespace(content=content, tool_calls=None)
                return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

        self.chat = SimpleNamespace(completions=_Completions())


def test_stream_falls_back_to_run_agent(monkeypatch):
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeFallbackClient("Fallback reply."))
    meta = {}
    events = list(agent.run_agent_stream("hello", [], meta))
    assert "".join(t for k, t in events if k == "token") == "Fallback reply."
    assert meta["tools_used"] == []
