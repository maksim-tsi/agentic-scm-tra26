import os
import sys
from typing import Any

import pytest
from langchain_core.messages import AIMessage


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


class _YaamStub:
    def __init__(self) -> None:
        self.closed = 0
        self.retrieve_calls: list[dict[str, Any]] = []
        self.finalize_calls: list[dict[str, Any]] = []

    def retrieve_l2_facts(
        self,
        *,
        session_id: str,
        agent_id: str,
        task_id: str,
        traceparent: str | None = None,
        **_: Any,
    ) -> list[Any]:
        self.retrieve_calls.append(
            {"session_id": session_id, "agent_id": agent_id, "task_id": task_id, "traceparent": traceparent}
        )
        return [{"fact": "F1", "source": "YAAM L2"}]

    def finalize_l4_artifact(
        self,
        *,
        session_id: str,
        agent_id: str,
        task_id: str,
        title: str,
        final_artifact: str,
        consensus_metadata: dict[str, Any] | None = None,
        traceparent: str | None = None,
        **_: Any,
    ) -> dict[str, Any] | None:
        self.finalize_calls.append(
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "task_id": task_id,
                "title": title,
                "final_artifact": final_artifact,
                "consensus_metadata": consensus_metadata,
                "traceparent": traceparent,
            }
        )
        return {"ok": True}

    def close(self) -> None:
        self.closed += 1


class _StructuredStub:
    def __init__(self, synthesis: Any):
        self._synthesis = synthesis
        self.invocations: list[Any] = []

    def invoke(self, messages: Any, config: Any = None) -> Any:
        self.invocations.append({"messages": messages, "config": config})
        return self._synthesis


class _ChatOpenAIStub:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def with_structured_output(self, schema: Any) -> _StructuredStub:
        synthesis = schema(
            evidence_table=[{"fact": "EOQ = 123", "source": "Tool:economic_order_quantity__x"}],
            final_answer="Answer citing (E1).",
        )
        return _StructuredStub(synthesis)


def test_finalizer_node_saves_l4_and_returns_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import finalizer as finalizer_mod

    yaam = _YaamStub()
    monkeypatch.setattr(finalizer_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(finalizer_mod, "_extract_traceparent", lambda: "tp")
    monkeypatch.setattr(finalizer_mod, "ChatOpenAI", _ChatOpenAIStub)

    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_MODEL", "m")

    state = {"task_data": {"task_id": "T1"}, "messages": [AIMessage(content="FINAL_EXECUTION_DONE: done")]}
    out = finalizer_mod.finalizer_node(state, {"configurable": {}})

    assert out["final_answer"] == "Answer citing (E1)."
    assert isinstance(out["evidence_table"], list) and out["evidence_table"][0]["fact"].startswith("EOQ")

    assert yaam.closed == 2
    assert yaam.retrieve_calls and yaam.retrieve_calls[0]["task_id"] == "T1"
    assert yaam.finalize_calls and yaam.finalize_calls[0]["task_id"] == "T1"
    meta = yaam.finalize_calls[0]["consensus_metadata"] or {}
    assert "evidence_table" in meta
    assert yaam.finalize_calls[0]["traceparent"] == "tp"

