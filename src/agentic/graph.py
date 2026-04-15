from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agentic.state import GraphState


def _get_message_tool_calls(msg: Any) -> list[Any]:
    if isinstance(msg, dict):
        tool_calls = msg.get("tool_calls")
        return list(tool_calls) if isinstance(tool_calls, list) else []

    tool_calls = getattr(msg, "tool_calls", None)
    if isinstance(tool_calls, list) and tool_calls:
        return tool_calls

    additional_kwargs = getattr(msg, "additional_kwargs", None)
    if isinstance(additional_kwargs, dict):
        tool_calls = additional_kwargs.get("tool_calls")
        return list(tool_calls) if isinstance(tool_calls, list) else []

    return []


def _get_message_content(msg: Any) -> str:
    if isinstance(msg, dict):
        content = msg.get("content")
        return content if isinstance(content, str) else ""
    content = getattr(msg, "content", None)
    return content if isinstance(content, str) else ""


def executor_router(state: GraphState) -> str:
    messages = state.get("messages", [])
    if not isinstance(messages, list) or not messages:
        return "executor_tools"

    last_msg = messages[-1]
    tool_calls = _get_message_tool_calls(last_msg)
    if tool_calls:
        return "executor_tools"

    content = _get_message_content(last_msg)
    if "FINAL_EXECUTION_DONE:" in content:
        return "finalizer"

    return "executor_tools"


def compile_graph(checkpointer: Any | None = None) -> CompiledStateGraph:
    builder: StateGraph = StateGraph(GraphState)

    from agentic.nodes.executor import executor_agent_node, executor_tools_node
    from agentic.nodes.finalizer import finalizer_node
    from agentic.nodes.planner import planner_node

    builder.add_node("planner", planner_node)
    builder.add_node("executor", executor_agent_node)
    builder.add_node("executor_tools", executor_tools_node)
    builder.add_node("finalizer", finalizer_node)

    builder.add_edge(START, "planner")
    builder.add_edge("planner", "executor")
    builder.add_edge("executor_tools", "executor")
    builder.add_conditional_edges("executor", executor_router)
    builder.add_edge("finalizer", END)

    return builder.compile(checkpointer=checkpointer)
