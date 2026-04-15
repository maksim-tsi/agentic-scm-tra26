import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


class _YaamStub:
    def __init__(self, results: list[Any]) -> None:
        self.results = results
        self.closed = False
        self.last_traceparent: str | None = None

    def query_l3_semantic(
        self,
        *,
        session_id: str,
        agent_id: str,
        nl_query: str,
        traceparent: str | None = None,
        **_: Any,
    ) -> list[Any]:
        self.last_traceparent = traceparent
        return list(self.results)

    def close(self) -> None:
        self.closed = True


class _OpenAIStub:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.last_extra_headers: dict[str, str] | None = None

        def _create(*, model: str, messages: list[dict[str, str]], extra_headers: dict[str, str] | None = None, **__: Any) -> Any:
            self.last_extra_headers = extra_headers
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="1) Step one\n2) Step two"))
                ]
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))


def test_planner_node_returns_messages_and_retrieved_context(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import planner as planner_mod

    yaam = _YaamStub(results=[{"k": "v"}])
    monkeypatch.setattr(planner_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(planner_mod, "_extract_traceparent", lambda: "tp")
    monkeypatch.setattr(planner_mod, "OpenAI", _OpenAIStub)

    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_MODEL", "m")

    state = {
        "task_data": {
            "task_id": "T1",
            "scenario_context": "Scenario",
            "agent_prompt": "Prompt",
        }
    }
    out = planner_mod.planner_node(state, {"configurable": {}})

    assert "messages" in out
    assert "retrieved_context" in out
    assert out["retrieved_context"] == [{"k": "v"}]
    assert yaam.closed is True
    assert yaam.last_traceparent == "tp"
    assert out["messages"][0].content.startswith("1)")


def test_planner_node_closes_yaam_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import planner as planner_mod

    yaam = _YaamStub(results=[])
    monkeypatch.setattr(planner_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(planner_mod, "_extract_traceparent", lambda: None)

    class _OpenAIFails(_OpenAIStub):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)

            def _create(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("LLM down")

            self.chat.completions.create = _create

    monkeypatch.setattr(planner_mod, "OpenAI", _OpenAIFails)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_MODEL", "m")

    state = {
        "task_data": {
            "task_id": "T1",
            "scenario_context": "Scenario",
            "agent_prompt": "Prompt",
        }
    }

    with pytest.raises(RuntimeError):
        planner_mod.planner_node(state, {"configurable": {}})

    assert yaam.closed is True


def test_planner_node_propagates_traceparent_to_openrouter(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import planner as planner_mod

    yaam = _YaamStub(results=[])
    monkeypatch.setattr(planner_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(planner_mod, "_extract_traceparent", lambda: "tp")

    openai = _OpenAIStub()
    monkeypatch.setattr(planner_mod, "OpenAI", lambda *a, **k: openai)

    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_MODEL", "m")

    state = {
        "task_data": {
            "task_id": "T1",
            "scenario_context": "Scenario",
            "agent_prompt": "Prompt",
        }
    }
    _ = planner_mod.planner_node(state, {"configurable": {}})

    assert openai.last_extra_headers == {"traceparent": "tp"}
