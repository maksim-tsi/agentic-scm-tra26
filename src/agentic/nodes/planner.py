from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from openai import OpenAI

from agentic.state import GraphState
from memory.yaam_client import YaamSemanticClient


PLANNER_SYSTEM_PROMPT = """\
Role: You are the Lead SCM Planner in a Multi-Agent System.
Goal: Analyze the logistics task and formulate a strict, step-by-step quantitative reasoning plan.

Rules of engagement (non-negotiable):
1) Do NOT attempt to calculate numbers yourself. You are prone to hallucination.
2) Rely entirely on the "Executor" agent who has access to deterministic Python tools for all calculations.
3) Incorporate any relevant insights from the provided "Historical Context" (L3 Memory) into your plan.
4) Output ONLY the step-by-step plan.

Formatting:
- Return a numbered list of steps.
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


def _openrouter_client(*, openrouter_api_key: str, base_url: str) -> OpenAI:
    default_headers: dict[str, str] = {}
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER") or None
    x_title = os.getenv("OPENROUTER_X_TITLE") or os.getenv("OPENROUTER_APP_TITLE") or "scm-cert-eval"
    if http_referer:
        default_headers["HTTP-Referer"] = http_referer
    if x_title:
        default_headers["X-Title"] = x_title

    return OpenAI(api_key=openrouter_api_key, base_url=base_url, default_headers=default_headers)


def planner_node(state: GraphState, config: RunnableConfig) -> dict:
    task_data = state.get("task_data")
    if not isinstance(task_data, dict):
        raise ValueError("planner_node requires state['task_data'] to be a dict")

    task_id = str(task_data.get("task_id") or "")
    if not task_id:
        raise ValueError("planner_node requires task_data['task_id']")

    session_id = task_id
    scenario_context = str(task_data.get("scenario_context") or "")
    agent_prompt = str(task_data.get("agent_prompt") or "")
    raw_task_text = f"{scenario_context}\n\n{agent_prompt}".strip()

    traceparent = _extract_traceparent()

    configurable = config.get("configurable", {}) or {}
    agent_id = str(configurable.get("agent_id") or "tra-scm-planner")

    yaam: YaamSemanticClient | None = None
    retrieved_l3_results: list[Any] = []
    try:
        yaam = YaamSemanticClient.from_env()
        retrieved_l3_results = yaam.query_l3_semantic(
            session_id=session_id,
            agent_id=agent_id,
            nl_query=raw_task_text,
            traceparent=traceparent,
        )
    finally:
        if yaam is not None:
            yaam.close()

    model_id = str(configurable.get("model_id") or os.getenv("OPENROUTER_MODEL") or "")
    if not model_id:
        raise RuntimeError("Missing model id: set config['configurable']['model_id'] or OPENROUTER_MODEL")

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
    if not openrouter_api_key:
        raise RuntimeError("Missing required env var: OPENROUTER_API_KEY")

    base_url = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    client = _openrouter_client(openrouter_api_key=openrouter_api_key, base_url=base_url)

    historical_context = json.dumps(retrieved_l3_results, ensure_ascii=False, indent=2) if retrieved_l3_results else "(none)"
    system_text = f"{PLANNER_SYSTEM_PROMPT}\n\nHistorical Context (L3 Memory):\n{historical_context}\n"

    system_msg = SystemMessage(content=system_text)
    human_msg = HumanMessage(content=raw_task_text)

    messages_payload = [
        {"role": "system", "content": str(system_msg.content)},
        {"role": "user", "content": str(human_msg.content)},
    ]

    extra_headers = {"traceparent": traceparent} if traceparent else None
    if extra_headers:
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=messages_payload,  # type: ignore[arg-type]
                temperature=0,
                extra_headers=extra_headers,
            )
        except TypeError:
            resp = client.chat.completions.create(
                model=model_id,
                messages=messages_payload,  # type: ignore[arg-type]
                temperature=0,
            )
    else:
        resp = client.chat.completions.create(
            model=model_id,
            messages=messages_payload,  # type: ignore[arg-type]
            temperature=0,
        )

    assistant_content = ""
    try:
        assistant_content = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"Planner LLM call returned unexpected response type: {type(resp).__name__}") from exc

    if not assistant_content:
        raise RuntimeError("Planner LLM call returned empty content")

    ai_response_message = AIMessage(content=assistant_content)
    return {"messages": [ai_response_message], "retrieved_context": retrieved_l3_results}
