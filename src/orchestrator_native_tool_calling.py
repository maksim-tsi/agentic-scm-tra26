from __future__ import annotations

import json
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, get_args, get_type_hints

from pydantic import BaseModel, ValidationError


RunMode = Literal["Naive", "Naive+Evidence", "Tools", "Tools+Evidence"]


MAX_VALIDATION_RETRIES = 5
MAX_TOOL_CYCLES = 10


@dataclass(frozen=True)
class TaskRow:
    task_id: str
    scenario_context: str
    agent_prompt: str
    t_shirt_size: str


@dataclass(frozen=True)
class ExecutionMetrics:
    syntax_errors_caught: int
    successful_retry_attempt: int
    tools_called: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "syntax_errors_caught": int(self.syntax_errors_caught),
            "successful_retry_attempt": int(self.successful_retry_attempt),
            "tools_called": list(self.tools_called),
        }


ToolCallable = Callable[[BaseModel], BaseModel]


def _get_trace_headers() -> dict[str, str]:
    """
    Best-effort OpenTelemetry trace propagation for provider HTTP calls.

    Returns a carrier dict that may include W3C headers (e.g., "traceparent") via
    `opentelemetry.propagate.inject`, plus a convenience "x-trace-id" hex value.
    """
    try:
        from opentelemetry import propagate, trace  # type: ignore
    except Exception:
        return {}

    carrier: dict[str, str] = {}
    try:
        propagate.inject(carrier)
    except Exception:
        pass

    try:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span is not None else None
        if ctx is not None and getattr(ctx, "is_valid", False) and getattr(ctx, "trace_id", 0):
            carrier.setdefault("x-trace-id", f"{int(ctx.trace_id):032x}")
    except Exception:
        pass

    return carrier


def load_tasks(path: str | Path) -> dict[str, TaskRow]:
    """
    Load benchmark tasks from a questions-only JSONL file.

    Contract: each JSON object has exactly these keys:
    - task_id
    - scenario_context
    - agent_prompt
    - t_shirt_size
    """
    expected = {"task_id", "scenario_context", "agent_prompt", "t_shirt_size"}
    resolved = Path(path)
    raw = resolved.read_text(encoding="utf-8").splitlines()

    tasks: dict[str, TaskRow] = {}
    for lineno, line in enumerate(raw, start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"Invalid JSONL row at line {lineno}: expected object")
        keys = set(row.keys())
        if keys != expected:
            raise ValueError(f"Invalid keys at line {lineno}: expected {sorted(expected)}, got {sorted(keys)}")

        task = TaskRow(
            task_id=str(row["task_id"]),
            scenario_context=str(row["scenario_context"]),
            agent_prompt=str(row["agent_prompt"]),
            t_shirt_size=str(row["t_shirt_size"]),
        )
        if task.task_id in tasks:
            raise ValueError(f"Duplicate task_id at line {lineno}: {task.task_id}")
        tasks[task.task_id] = task

    return tasks


def _tool_alias(fn: Callable[..., Any]) -> str:
    return f"{fn.__module__.split('.')[-1]}__{fn.__name__}"


def _tool_description(fn: Callable[..., Any]) -> str:
    doc = (fn.__doc__ or "").strip()
    if not doc:
        return "Deterministic SCM tool."
    return doc.splitlines()[0].strip() or "Deterministic SCM tool."


def build_tool_registry(
    active_tools: list[Callable[..., Any]],
) -> tuple[list[dict[str, Any]], dict[str, ToolCallable], dict[str, type[BaseModel]]]:
    """
    Build the OpenAI tools schema list and local allowlist for tool execution.

    Returns:
    - tool_schemas: list[{"type":"function","function":{...}}]
    - name_to_callable: alias -> python function (callable(Input)->Output)
    - name_to_input_model: alias -> Pydantic Input model type
    """
    tool_schemas: list[dict[str, Any]] = []
    name_to_callable: dict[str, ToolCallable] = {}
    name_to_input_model: dict[str, type[BaseModel]] = {}

    for fn in active_tools:
        alias = _tool_alias(fn)
        if alias in name_to_callable:
            raise ValueError(f"Duplicate tool alias: {alias}")

        module = importlib.import_module(fn.__module__)

        # Prefer the strict "single Pydantic Input parameter" contract when present.
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
            # Some legacy tools export callables that take primitives, but the module still defines
            # a Pydantic input schema (InputSchema/Input). We enforce the Pydantic boundary at the
            # orchestrator layer by validating against that model and adapting the call.
            for candidate in ("InputSchema", "Input"):
                cls = getattr(module, candidate, None)
                if isinstance(cls, type) and issubclass(cls, BaseModel):
                    input_model = cls
                    break

        if input_model is None:
            raise ValueError(f"Tool does not expose a Pydantic input schema: {alias}")

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

        if output_model is None:
            raise ValueError(f"Tool does not expose a Pydantic output schema: {alias}")

        def _wrap_tool(
            raw_fn: Callable[..., Any],
            *,
            in_model: type[BaseModel],
            out_model: type[BaseModel],
            pass_input_model_directly: bool,
        ) -> ToolCallable:
            def _wrapped(input_data: BaseModel) -> BaseModel:
                if not isinstance(input_data, in_model):
                    # Defensive: orchestrator should have already validated with in_model.
                    input_data = in_model.model_validate(input_data)
                if pass_input_model_directly:
                    result = raw_fn(input_data)  # type: ignore[misc]
                else:
                    kwargs = input_data.model_dump(exclude_none=True)
                    result = raw_fn(**kwargs) if kwargs else raw_fn()  # type: ignore[misc]

                if isinstance(result, BaseModel):
                    return result
                if isinstance(result, dict):
                    return out_model.model_validate(result)

                fields = list(out_model.model_fields.keys())
                if len(fields) == 1:
                    return out_model(**{fields[0]: result})
                raise ValueError(f"Tool returned non-object value that cannot populate {out_model.__name__}")

            return _wrapped

        wrapped_callable = _wrap_tool(
            fn,
            in_model=input_model,
            out_model=output_model,
            pass_input_model_directly=pass_model_directly,
        )

        schema = {
            "type": "function",
            "function": {
                "name": alias,
                "description": _tool_description(fn),
                "parameters": input_model.model_json_schema(),
            },
        }
        tool_schemas.append(schema)
        name_to_callable[alias] = wrapped_callable
        name_to_input_model[alias] = input_model

    return tool_schemas, name_to_callable, name_to_input_model


def _coerce_run_mode(run_mode: str) -> RunMode:
    allowed = set(get_args(RunMode))
    if run_mode not in allowed:
        raise ValueError(f"Invalid run_mode: {run_mode!r} (allowed: {sorted(allowed)})")
    return run_mode  # type: ignore[return-value]


def _format_validation_error(err: ValidationError, *, tool_name: str) -> str:
    return f"Tool call validation failed for {tool_name}:\n{err}"


def _messages_for_task(task: TaskRow, run_mode: RunMode) -> list[dict[str, Any]]:
    # Keep this minimal: the benchmark prompt already contains the question; scenario context is provided separately.
    system = (
        "You are an expert SCM agent. Follow instructions precisely.\n"
        "When tools are available, prefer calling tools instead of hand calculations.\n"
        "When a tool call fails with a validation error, correct the payload and retry.\n"
        "Return the final answer as plain text."
    )

    evidence_note = ""
    if run_mode in ("Naive+Evidence", "Tools+Evidence"):
        evidence_note = (
            "\n\nEVIDENCE_TABLE (required for this run mode):\n"
            "Before any calculations or conclusions, extract the needed facts into a Markdown table with columns:\n"
            "| Fact | Source snippet | Normalized value | Units | Role/use in solution |\n"
            "Then proceed to solve the task."
        )

    user = (
        f"RUN_MODE: {run_mode}\n\n"
        f"SCENARIO_CONTEXT:\n{task.scenario_context}\n\n"
        f"TASK:\n{task.agent_prompt}\n"
        f"{evidence_note}\n"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_assistant_text(resp: Any) -> str:
    try:
        msg = resp.choices[0].message
    except Exception:
        return ""
    return (getattr(msg, "content", None) or "") or ""


def _extract_tool_calls(resp: Any) -> list[Any]:
    try:
        msg = resp.choices[0].message
    except Exception:
        return []
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls:
        return []
    return list(tool_calls)


def _assistant_message_with_tool_calls(resp: Any) -> dict[str, Any]:
    """
    Convert the provider response into an assistant message payload that includes tool_calls.

    This is required for correct tool-call chaining: the next request must include the assistant
    tool_call message followed by tool result messages.
    """
    msg = resp.choices[0].message
    content = (getattr(msg, "content", None) or "") or None
    tool_calls = getattr(msg, "tool_calls", None) or []
    rendered_tool_calls: list[dict[str, Any]] = []
    for tc in tool_calls:
        fn_obj = getattr(tc, "function", None)
        rendered_tool_calls.append(
            {
                "id": getattr(tc, "id", None),
                "type": getattr(tc, "type", None) or "function",
                "function": {
                    "name": getattr(fn_obj, "name", None) if fn_obj else None,
                    "arguments": getattr(fn_obj, "arguments", None) if fn_obj else None,
                },
            }
        )
    payload: dict[str, Any] = {"role": "assistant", "tool_calls": rendered_tool_calls}
    if content is not None:
        payload["content"] = content
    return payload


def run_task(
    *,
    task: TaskRow,
    run_mode: str,
    model_id: str,
    openai_client: Any,
    tool_schemas: list[dict[str, Any]],
    name_to_callable: dict[str, ToolCallable],
    name_to_input_model: dict[str, type[BaseModel]],
) -> tuple[str, ExecutionMetrics]:
    """
    Execute one task using the RFC 001 native tool-calling pipeline.

    Returns:
    - raw_response: final assistant content (or "" on failure)
    - execution_metrics: syntax_errors_caught, successful_retry_attempt, tools_called
    """
    mode = _coerce_run_mode(run_mode)

    try:
        from opentelemetry import trace  # type: ignore

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("session.id", f"task-{task.task_id}")
    except Exception:
        pass

    if mode in ("Naive", "Naive+Evidence"):
        messages = _messages_for_task(task, mode)
        trace_headers = _get_trace_headers()
        if trace_headers:
            try:
                resp = openai_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0,
                    extra_headers=trace_headers,
                )
            except TypeError:
                resp = openai_client.chat.completions.create(model=model_id, messages=messages, temperature=0)
        else:
            resp = openai_client.chat.completions.create(model=model_id, messages=messages, temperature=0)
        content = _extract_assistant_text(resp)
        return content, ExecutionMetrics(syntax_errors_caught=0, successful_retry_attempt=0, tools_called=[])

    messages = _messages_for_task(task, mode)
    syntax_errors_caught = 0
    successful_retry_attempt = 0
    tools_called: list[str] = []

    validation_attempt = 0
    tool_cycles = 0

    while True:
        tool_cycles += 1
        if tool_cycles > MAX_TOOL_CYCLES:
            return "", ExecutionMetrics(
                syntax_errors_caught=syntax_errors_caught,
                successful_retry_attempt=successful_retry_attempt,
                tools_called=tools_called,
            )

        trace_headers = _get_trace_headers()
        if trace_headers:
            try:
                resp = openai_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    temperature=0,
                    extra_headers=trace_headers,
                )
            except TypeError:
                resp = openai_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    temperature=0,
                )
        else:
            resp = openai_client.chat.completions.create(
                model=model_id,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0,
            )

        tool_calls = _extract_tool_calls(resp)
        if not tool_calls:
            content = _extract_assistant_text(resp)
            return content, ExecutionMetrics(
                syntax_errors_caught=syntax_errors_caught,
                successful_retry_attempt=successful_retry_attempt,
                tools_called=tools_called,
            )

        # Always append the assistant tool_call message (required for correct tool chaining).
        messages.append(_assistant_message_with_tool_calls(resp))

        # Validate all tool calls in this turn. A ValidationError triggers the RFC001 retry loop.
        validation_attempt += 1
        validation_errors_this_turn = 0  # ValidationError count only (RFC002)

        validated_calls: list[tuple[str, str, BaseModel]] = []
        for tool_call in tool_calls:
            fn_obj = getattr(tool_call, "function", None)
            tool_name = getattr(fn_obj, "name", None) if fn_obj else None
            arg_str = getattr(fn_obj, "arguments", None) if fn_obj else None
            tool_call_id = getattr(tool_call, "id", None) or ""

            if not isinstance(tool_name, str) or tool_name not in name_to_callable:
                # Unknown tool request; treat as a hard failure (walled garden).
                return "", ExecutionMetrics(
                    syntax_errors_caught=syntax_errors_caught,
                    successful_retry_attempt=successful_retry_attempt,
                    tools_called=tools_called,
                )

            try:
                args_obj = json.loads(arg_str or "{}")
            except json.JSONDecodeError as exc:
                # Not a Pydantic ValidationError, but still needs correction.
                messages.append({"role": "user", "content": f"Tool call arguments were not valid JSON for {tool_name}: {exc}"})
                continue

            input_model = name_to_input_model[tool_name]
            try:
                validated = input_model.model_validate(args_obj)
            except ValidationError as exc:
                validation_errors_this_turn += 1
                messages.append({"role": "user", "content": _format_validation_error(exc, tool_name=tool_name)})
                continue

            validated_calls.append((tool_name, tool_call_id, validated))

        if validation_errors_this_turn or len(validated_calls) != len(tool_calls):
            syntax_errors_caught += validation_errors_this_turn
            if validation_attempt >= MAX_VALIDATION_RETRIES:
                return "", ExecutionMetrics(
                    syntax_errors_caught=syntax_errors_caught,
                    successful_retry_attempt=0,
                    tools_called=tools_called,
                )
            continue

        if successful_retry_attempt == 0:
            successful_retry_attempt = validation_attempt

        # Execute validated tools and append results as tool messages.
        for tool_name, tool_call_id, validated_input in validated_calls:
            tools_called.append(tool_name)
            fn = name_to_callable[tool_name]
            try:
                output = fn(validated_input)
                payload = output.model_dump() if isinstance(output, BaseModel) else output
                content = json.dumps(payload, ensure_ascii=False)
            except Exception as exc:
                content = f"Tool execution error for {tool_name}: {type(exc).__name__}: {exc}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content,
                }
            )
