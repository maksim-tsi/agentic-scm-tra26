import os
import sys
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


class _YaamStub:
    def __init__(self) -> None:
        self.closed = False
        self.calls: list[dict[str, Any]] = []

    def store_l2_fact(
        self,
        *,
        session_id: str,
        agent_id: str,
        task_id: str,
        content: str,
        traceparent: str | None = None,
        **_: Any,
    ) -> dict[str, Any] | None:
        self.calls.append(
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "task_id": task_id,
                "content": content,
                "traceparent": traceparent,
            }
        )
        return {"ok": True}

    def close(self) -> None:
        self.closed = True


def test_store_intermediate_fact_uses_task_id_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    yaam = _YaamStub()
    monkeypatch.setattr(executor_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(executor_mod, "_extract_traceparent", lambda: "tp")

    ai = AIMessage(
        content="store",
        tool_calls=[
            {"name": "store_intermediate_fact", "args": {"fact": "fact-1"}, "id": "1", "type": "tool_call"}
        ],
    )
    out = executor_mod.executor_tools_node.invoke(
        {"messages": [ai], "task_data": {"task_id": "T1", "scenario_context": "", "agent_prompt": ""}},
        config={"configurable": {"__pregel_runtime": Runtime()}},
    )

    msgs = out.get("messages") if isinstance(out, dict) else None
    assert isinstance(msgs, list) and msgs, "ToolNode should return tool messages"
    assert yaam.closed is True
    assert yaam.calls and yaam.calls[0]["session_id"] == "T1" and yaam.calls[0]["task_id"] == "T1"
    assert yaam.calls[0]["agent_id"] == "tra-scm-executor"
    assert yaam.calls[0]["content"] == "fact-1"
    assert yaam.calls[0]["traceparent"] == "tp"


def test_store_intermediate_fact_env_missing_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    def _raise() -> Any:
        raise ValueError("Missing required env var: YAAM_SEMANTIC_GATEWAY_URL")

    monkeypatch.setattr(executor_mod.YaamSemanticClient, "from_env", staticmethod(_raise))

    ai = AIMessage(
        content="store",
        tool_calls=[
            {"name": "store_intermediate_fact", "args": {"fact": "fact-1"}, "id": "1", "type": "tool_call"}
        ],
    )
    out = executor_mod.executor_tools_node.invoke(
        {"messages": [ai], "task_data": {"task_id": "T1", "scenario_context": "", "agent_prompt": ""}},
        config={"configurable": {"__pregel_runtime": Runtime()}},
    )
    msgs = out.get("messages") if isinstance(out, dict) else None
    assert isinstance(msgs, list) and msgs
    assert "SKIPPED" in str(getattr(msgs[-1], "content", ""))


def test_wrapped_tool_validation_error_is_visible() -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    tool_name = "economic_order_quantity__calculate_total_annual_inventory_cost"
    assert tool_name in executor_mod.executor_tools_node.tools_by_name

    ai = AIMessage(
        content="call",
        tool_calls=[
            {
                "name": tool_name,
                "args": {"annual_demand": "not-a-number"},
                "id": "1",
                "type": "tool_call",
            }
        ],
    )
    out = executor_mod.executor_tools_node.invoke(
        {"messages": [ai], "task_data": {"task_id": "T1"}},
        config={"configurable": {"__pregel_runtime": Runtime()}},
    )
    msgs = out.get("messages") if isinstance(out, dict) else None
    assert isinstance(msgs, list) and msgs
    assert str(getattr(msgs[-1], "content", "")).startswith("Validation Error:")
