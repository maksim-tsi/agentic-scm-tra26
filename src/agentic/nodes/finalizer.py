from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agentic.state import GraphState
from memory.yaam_client import YaamSemanticClient


class EvidenceItem(BaseModel):
    fact: str = Field(description="A verified quantitative fact or result from the tool execution")
    source: str = Field(description="The source of the fact (e.g., 'EOQ Tool', 'L3 Memory')")


class FinalSynthesis(BaseModel):
    evidence_table: list[EvidenceItem] = Field(
        description="Strict tabulation of all facts required for the final answer"
    )
    final_answer: str = Field(description="The final comprehensive answer to the user's task, heavily citing the evidence table")


FINALIZER_SYSTEM_PROMPT = """\
Role: You are the SCM Finalizer Node.
Goal: Close the retrieval–reasoning gap by producing:
1) An Evidence Table of ONLY verified facts, metrics, or strategic categorizations (e.g., SWOT, Kraljic).
2) A final comprehensive answer that cites the Evidence Table entries.

Non-negotiable rules:
- Only include facts/results that are explicitly present in tool outputs, working-memory facts (YAAM L2), or provided context (YAAM L3 results). Do not ignore qualitative analytical results.
- Every evidence row must have a clear source label:
  - Tool results: "Tool:<tool_name>"
  - YAAM L2 facts: "YAAM L2"
  - L3 context: "L3 Memory"
- The final answer MUST cite evidence rows by index, e.g. "(E1)", "(E2)", when evidence is available.
- If no quantitative evidence exists, return an empty evidence_table and explicitly state that no citations are possible.
- Do not invent values. If a required value is missing, say so and cite the absence.

Output must match the provided JSON schema exactly.
"""


def _extract_traceparent() -> str | None:
    try:
        from opentelemetry import propagate  # type: ignore
    except Exception:
        return None

    carrier: dict[str, str] = {}
    try:
        propagate.inject(carrier)
    except Exception:
        return None

    value = carrier.get("traceparent")
    return value if isinstance(value, str) and value else None


def _extract_json_object(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1].strip()
    return cleaned


def finalizer_node(state: GraphState, config: RunnableConfig) -> dict:
    task_data = state.get("task_data")
    if not isinstance(task_data, dict):
        raise ValueError("finalizer_node requires state['task_data'] to be a dict")

    task_id = str(task_data.get("task_id") or "")
    if not task_id:
        raise ValueError("finalizer_node requires task_data['task_id']")

    messages = state.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("finalizer_node requires state['messages'] to be a list")

    configurable = config.get("configurable", {}) or {}
    agent_id = str(configurable.get("agent_id") or "tra-scm-finalizer")

    model_id = str(configurable.get("model_id") or os.getenv("OPENROUTER_MODEL") or "")
    if not model_id:
        raise RuntimeError("Missing model id: set config['configurable']['model_id'] or OPENROUTER_MODEL")

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
    if not openrouter_api_key:
        raise RuntimeError("Missing required env var: OPENROUTER_API_KEY")

    base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    traceparent = _extract_traceparent()
    default_headers = {"traceparent": traceparent} if traceparent else None

    llm = ChatOpenAI(
        model=model_id,
        api_key=openrouter_api_key,
        base_url=base_url,
        temperature=0,
        default_headers=default_headers,
    )
    structured_llm = llm.with_structured_output(FinalSynthesis)

    session_id = task_id

    l2_facts: list[Any] = []
    yaam_l2: YaamSemanticClient | None = None
    try:
        yaam_l2 = YaamSemanticClient.from_env()
        l2_facts = yaam_l2.retrieve_l2_facts(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            traceparent=traceparent,
        )
    finally:
        if yaam_l2 is not None:
            yaam_l2.close()

    retrieved_context = state.get("retrieved_context", [])
    if not isinstance(retrieved_context, list):
        retrieved_context = []

    l2_blob = json.dumps(l2_facts, ensure_ascii=False, indent=2) if l2_facts else "(none)"
    l3_blob = json.dumps(retrieved_context, ensure_ascii=False, indent=2) if retrieved_context else "(none)"

    system_msg = SystemMessage(
        content=(
            f"{FINALIZER_SYSTEM_PROMPT}\n\n"
            f"YAAM L2 Facts (working memory):\n{l2_blob}\n\n"
            f"L3 Memory Context:\n{l3_blob}\n"
        )
    )

    try:
        synthesis = structured_llm.invoke([system_msg, *messages], config=config)
        if not isinstance(synthesis, FinalSynthesis):
            synthesis = FinalSynthesis.model_validate(synthesis)
    except Exception:
        raw_msg = llm.invoke([system_msg, *messages], config=config)
        raw_text = _extract_json_object(str(getattr(raw_msg, "content", "")))
        synthesis = FinalSynthesis.model_validate_json(raw_text)

    yaam_l4: YaamSemanticClient | None = None
    try:
        yaam_l4 = YaamSemanticClient.from_env()
        yaam_l4.finalize_l4_artifact(
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            title=f"Consensus Report: {task_id}",
            final_artifact=synthesis.final_answer,
            consensus_metadata={"evidence_table": [item.model_dump() for item in synthesis.evidence_table]},
            traceparent=traceparent,
        )
    finally:
        if yaam_l4 is not None:
            yaam_l4.close()

    return {
        "evidence_table": [item.model_dump() for item in synthesis.evidence_table],
        "final_answer": synthesis.final_answer,
    }
