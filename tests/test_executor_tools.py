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


def test_successful_tool_call_auto_stores_l2_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    yaam = _YaamStub()
    monkeypatch.setattr(executor_mod.YaamSemanticClient, "from_env", staticmethod(lambda: yaam))
    monkeypatch.setattr(executor_mod, "_extract_traceparent", lambda: "tp")

    tool_name = "economic_order_quantity__calculate_total_annual_inventory_cost"
    ai = AIMessage(
        content="call",
        tool_calls=[
            {
                "name": tool_name,
                "args": {
                    "annual_demand": 1000.0,
                    "order_quantity": 100.0,
                    "order_cost": 50.0,
                    "holding_cost_per_unit": 2.0,
                },
                "id": "1",
                "type": "tool_call",
            }
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
    assert yaam.calls[0]["content"].startswith(f"Tool {tool_name} returned: ")
    assert "total_annual_cost" in yaam.calls[0]["content"]
    assert yaam.calls[0]["traceparent"] == "tp"


def test_yaam_failure_does_not_change_tool_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    def _raise() -> Any:
        raise ValueError("Missing required env var: YAAM_SEMANTIC_GATEWAY_URL")

    monkeypatch.setattr(executor_mod.YaamSemanticClient, "from_env", staticmethod(_raise))

    tool_name = "economic_order_quantity__calculate_total_annual_inventory_cost"
    ai = AIMessage(
        content="call",
        tool_calls=[
            {
                "name": tool_name,
                "args": {
                    "annual_demand": 1000.0,
                    "order_quantity": 100.0,
                    "order_cost": 50.0,
                    "holding_cost_per_unit": 2.0,
                },
                "id": "1",
                "type": "tool_call",
            }
        ],
    )
    out = executor_mod.executor_tools_node.invoke(
        {"messages": [ai], "task_data": {"task_id": "T1", "scenario_context": "", "agent_prompt": ""}},
        config={"configurable": {"__pregel_runtime": Runtime()}},
    )
    msgs = out.get("messages") if isinstance(out, dict) else None
    assert isinstance(msgs, list) and msgs
    content = str(getattr(msgs[-1], "content", ""))
    assert "total_annual_cost" in content
    assert not content.startswith("Tool Error:")


def test_store_intermediate_fact_tool_is_not_exposed() -> None:
    _ensure_src_on_path()
    from agentic.nodes import executor as executor_mod

    assert "store_intermediate_fact" not in executor_mod.executor_tools_node.tools_by_name


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
