from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, get_type_hints

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools.structured import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, ValidationError

from agentic.state import GraphState
from memory.yaam_client import YaamSemanticClient
from tools import ACTIVE_TOOLS


logger = logging.getLogger(__name__)


EXECUTOR_SYSTEM_PROMPT = """\
You are the Lead SCM Executor in a Multi-Agent System.
Your Goal: Execute the step-by-step plan provided by the Planner.

Rules of the Walled Garden:
1. You CANNOT calculate any math yourself. You MUST use the provided tools for every quantitative step.
2. If a tool returns a validation error (Pydantic), analyze the error, correct your parameters, and call the tool again.
3. When all steps in the plan are fully resolved, output a message starting with "FINAL_EXECUTION_DONE:" followed by a brief summary of the findings.
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


def _tool_alias(fn: Callable[..., Any]) -> str:
    return f"{fn.__module__.split('.')[-1]}__{fn.__name__}"


def _tool_description(fn: Callable[..., Any]) -> str:
    doc = (fn.__doc__ or "").strip()
    if not doc:
        return "Deterministic SCM tool."
    return doc.splitlines()[0].strip() or "Deterministic SCM tool."


def _serialize_tool_output(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        value = value.model_dump(exclude_none=True)
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _resolve_tool_models(
    fn: Callable[..., Any],
) -> tuple[type[BaseModel], bool, type[BaseModel] | None]:
    """
    Returns (input_model, pass_model_directly, output_model).

    Mirrors the repo's orchestrator heuristics:
    - Prefer BaseModel parameter annotation on the function.
    - Otherwise, look for InputSchema/Input on the tool module.
    - Output similarly via return annotation or OutputSchema/Output on the module.
    """
    import importlib

    module = importlib.import_module(fn.__module__)
    hints = get_type_hints(fn)

    input_models: list[type[BaseModel]] = []
    for name, t in hints.items():
        if name == "return":
            continue
        if isinstance(t, type) and issubclass(t, BaseModel):
            input_models.append(t)

    input_model: type[BaseModel] | None = input_models[0] if len(input_models) == 1 else None
    pass_model_directly = input_model is not None
    if input_model is None:
        for candidate in ("InputSchema", "Input"):
            cls = getattr(module, candidate, None)
            if isinstance(cls, type) and issubclass(cls, BaseModel):
                input_model = cls
                break

    if input_model is None:
        raise ValueError(f"Tool does not expose a Pydantic input schema: {_tool_alias(fn)}")

    output_model: type[BaseModel] | None = None
    ret_t = hints.get("return")
    if isinstance(ret_t, type) and issubclass(ret_t, BaseModel):
        output_model = ret_t
    else:
        for candidate in ("OutputSchema", "Output"):
            cls = getattr(module, candidate, None)
            if isinstance(cls, type) and issubclass(cls, BaseModel):
                output_model = cls
                break

    return input_model, pass_model_directly, output_model


def _resolve_task_id_from_runtime(runtime: ToolRuntime | None) -> str | None:
    if runtime is None:
        return None

    try:
        state = getattr(runtime, "state", None)
        if isinstance(state, dict):
            task_data = state.get("task_data")
            if isinstance(task_data, dict):
                candidate = task_data.get("task_id")
                if candidate:
                    return str(candidate)
    except Exception:
        pass

    try:
        cfg = getattr(runtime, "config", None)
        if isinstance(cfg, dict):
            configurable = cfg.get("configurable", {}) or {}
            candidate = configurable.get("task_id")
            if candidate:
                return str(candidate)
    except Exception:
        pass

    return None


def _best_effort_store_tool_result(*, tool_alias: str, serialized_result: str, runtime: ToolRuntime | None) -> None:
    task_id = _resolve_task_id_from_runtime(runtime)
    if not task_id:
        logger.debug("Skipping YAAM L2 write for %s: missing task_id in runtime context", tool_alias)
        return

    traceparent = _extract_traceparent()
    yaam: YaamSemanticClient | None = None
    try:
        yaam = YaamSemanticClient.from_env()
        _ = yaam.store_l2_fact(
            session_id=task_id,
            agent_id="tra-scm-executor",
            task_id=task_id,
            content=f"Tool {tool_alias} returned: {serialized_result}",
            traceparent=traceparent,
        )
    except Exception as e:
        logger.warning("YAAM L2 write failed for %s: %s: %s", tool_alias, type(e).__name__, e)
    finally:
        if yaam is not None:
            try:
                yaam.close()
            except Exception:
                pass


def _wrap_active_tool(fn: Callable[..., Any]) -> StructuredTool:
    alias = _tool_alias(fn)
    description = _tool_description(fn)
    input_model, pass_model_directly, output_model = _resolve_tool_models(fn)
    json_schema = input_model.model_json_schema()

    def wrapped_tool(runtime: ToolRuntime | None = None, **kwargs: Any) -> str:
        # IMPORTANT for self-correction: do not let ValidationError bubble into ToolNode.
        try:
            input_obj = input_model.model_validate(kwargs)
        except ValidationError as e:
            return f"Validation Error: {str(e)}"

        try:
            if pass_model_directly:
                result = fn(input_obj)  # type: ignore[misc]
            else:
                call_kwargs = input_obj.model_dump(exclude_none=True)
                result = fn(**call_kwargs) if call_kwargs else fn()  # type: ignore[misc]
        except Exception as e:
            return f"Tool Error: {type(e).__name__}: {e}"

        payload: str
        if isinstance(result, BaseModel):
            payload = _serialize_tool_output(result.model_dump(exclude_none=True))
        elif isinstance(result, dict):
            payload = _serialize_tool_output(result)
        elif output_model is not None:
            fields = list(output_model.model_fields.keys())
            if len(fields) == 1:
                try:
                    coerced = output_model(**{fields[0]: result})
                    payload = _serialize_tool_output(coerced.model_dump(exclude_none=True))
                except Exception:
                    payload = _serialize_tool_output(result)
            else:
                payload = _serialize_tool_output(result)
        else:
            payload = _serialize_tool_output(result)

        _best_effort_store_tool_result(tool_alias=alias, serialized_result=payload, runtime=runtime)
        return payload

    return StructuredTool.from_function(
        func=wrapped_tool,
        name=alias,
        description=description,
        args_schema=json_schema,
        infer_schema=False,
    )


wrapped_active_tools = [_wrap_active_tool(fn) for fn in ACTIVE_TOOLS]
all_tools = [*wrapped_active_tools]


def executor_agent_node(state: GraphState, config: RunnableConfig) -> dict:
    messages = state.get("messages", [])
    if not isinstance(messages, list):
        raise ValueError("executor_agent_node requires state['messages'] to be a list")

    has_system = any(isinstance(m, SystemMessage) for m in messages)
    if not has_system:
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT), *messages]

    configurable = config.get("configurable", {}) or {}
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
    llm_with_tools = llm.bind_tools(all_tools)
    response = llm_with_tools.invoke(messages, config=config)
    return {"messages": [response]}


def _tool_error_handler(e: Exception) -> str:
    return str(e)


executor_tools_node = ToolNode(all_tools, handle_tool_errors=_tool_error_handler)

