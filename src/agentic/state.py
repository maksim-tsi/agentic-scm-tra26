from __future__ import annotations

from typing import Any, Annotated, TypedDict

from langgraph.graph.message import add_messages


class GraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    task_data: dict
    working_memory: list
    retrieved_context: list
    evidence_table: list[dict[str, Any]] | None
    final_answer: str
    execution_metrics: dict
