"""Agent-loop tests with a fully mocked Sarvam/OpenAI client — no network, no key.

Exercises the runtime: tool dispatch round-trip, malformed tool-args handling, and the
turn-cap guard. The tools it dispatches to are the curated ones (no network).
"""
from __future__ import annotations

from types import SimpleNamespace

from src import agent


def _tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def _response(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class FakeClient:
    """Returns scripted responses in order; the last one repeats if overrun."""
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = 0

        outer = self

        class _Completions:
            def create(self, **kwargs):
                i = min(outer.calls, len(outer._scripted) - 1)
                outer.calls += 1
                return outer._scripted[i]

        self.chat = SimpleNamespace(completions=_Completions())


def test_tool_round_trip(monkeypatch):
    scripted = [
        _response(tool_calls=[_tool_call("c1", "get_crop_advisory", '{"crop": "wheat"}')]),
        _response(content="Sow wheat, irrigate at day 21."),
    ]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeClient(scripted))
    out = agent.run_agent("advice for wheat?")
    assert out["reply"] == "Sow wheat, irrigate at day 21."
    assert out["tool_calls"] == ["get_crop_advisory"]
    assert out["tool_results"][0]["name"] == "get_crop_advisory"
    assert "nitrogen" in out["tool_results"][0]["result"]["advisory"].lower()
    assert out["turns"] == 2


def test_malformed_tool_args_do_not_crash(monkeypatch):
    scripted = [
        _response(tool_calls=[_tool_call("c1", "get_crop_advisory", "{not valid json")]),
        _response(content="Here is some advice."),
    ]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeClient(scripted))
    out = agent.run_agent("advice?")
    # bad JSON -> args {} -> missing required arg -> tool returns an error dict
    assert "error" in out["tool_results"][0]["result"]
    assert out["reply"] == "Here is some advice."


def test_turn_cap_guard(monkeypatch):
    # model that never stops calling tools
    looping = [_response(tool_calls=[_tool_call("c1", "get_crop_advisory", '{"crop": "wheat"}')])]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeClient(looping))
    out = agent.run_agent("loop forever")
    assert out["turns"] == agent.MAX_TURNS
    assert out["reply"].lower().startswith("sorry")


def test_no_tool_direct_answer(monkeypatch):
    scripted = [_response(content="Namaste, I am Kisan Mitra.")]
    monkeypatch.setattr(agent, "_oai_client", lambda: FakeClient(scripted))
    out = agent.run_agent("who are you?")
    assert out["tool_calls"] == []
    assert "Kisan Mitra" in out["reply"]
    assert out["turns"] == 1
