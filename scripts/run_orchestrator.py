from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, get_args

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator_native_tool_calling import RunMode, TaskRow, build_tool_registry, load_tasks, run_task


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class OrchestratorConfig:
    model_id: str
    run_mode: RunMode
    output_jsonl: Path
    task_id: str | None
    limit: int | None
    openrouter_base_url: str
    openrouter_api_key: str
    phoenix_collector_endpoint: str
    phoenix_project_name: str
    phoenix_api_key: str | None
    phoenix_client_headers: dict[str, str]


def _parse_header_kv_pairs(raw: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in (part.strip() for part in raw.split(",")):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value
    return headers


def _substitute_env_vars(template: str) -> str:
    out = template
    for var_name in ("DEV_NODE_IP", "PHOENIX_PORT"):
        value = os.getenv(var_name)
        if value:
            out = out.replace(f"${{{var_name}}}", value)
            out = out.replace(f"${var_name}", value)
    return out


def _resolve_phoenix_collector_endpoint() -> str:
    raw = os.getenv("PHOENIX_COLLECTOR_ENDPOINT") or ""
    if raw:
        return _substitute_env_vars(raw)

    dev_node_ip = os.getenv("DEV_NODE_IP")
    if not dev_node_ip:
        raise RuntimeError("Missing required env var: DEV_NODE_IP (needed to build PHOENIX_COLLECTOR_ENDPOINT)")

    phoenix_port = os.getenv("PHOENIX_PORT") or "6006"
    return f"http://{dev_node_ip}:{phoenix_port}/v1/traces"


def _load_config(argv: list[str]) -> OrchestratorConfig:
    parser = argparse.ArgumentParser(description="Native tool-calling orchestrator (RFC001 + RFC002).")
    parser.add_argument("--model-id", default=None, help="Model identifier (default: OPENROUTER_MODEL).")
    parser.add_argument(
        "--run-mode",
        default="Tools",
        choices=list(get_args(RunMode)),
        help="Run mode (RFC000/RFC002).",
    )
    parser.add_argument("--task-id", default=None, help="Run a single task by ID.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N tasks.")
    parser.add_argument(
        "--output-jsonl",
        default="outputs/evaluation_results.jsonl",
        help="Path to append RFC002 JSONL results.",
    )
    args = parser.parse_args(argv)

    load_dotenv()

    model_id = args.model_id or os.getenv("OPENROUTER_MODEL") or ""
    if not model_id:
        raise RuntimeError("Model not set. Provide --model-id or set OPENROUTER_MODEL.")

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
    if not openrouter_api_key:
        raise RuntimeError("Missing required env var: OPENROUTER_API_KEY")

    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL

    phoenix_collector_endpoint = _resolve_phoenix_collector_endpoint()
    phoenix_project_name = os.getenv("PHOENIX_PROJECT_NAME") or "scm-cert-eval-sandbox"

    phoenix_api_key = os.getenv("PHOENIX_API_KEY") or None
    phoenix_client_headers_raw = os.getenv("PHOENIX_CLIENT_HEADERS") or ""
    phoenix_client_headers = _parse_header_kv_pairs(phoenix_client_headers_raw)
    if phoenix_api_key and "Authorization" not in phoenix_client_headers:
        phoenix_client_headers["Authorization"] = f"Bearer {phoenix_api_key}"

    output_jsonl = Path(args.output_jsonl)

    return OrchestratorConfig(
        model_id=model_id,
        run_mode=args.run_mode,  # type: ignore[arg-type]
        output_jsonl=output_jsonl,
        task_id=args.task_id,
        limit=args.limit,
        openrouter_base_url=openrouter_base_url,
        openrouter_api_key=openrouter_api_key,
        phoenix_collector_endpoint=phoenix_collector_endpoint,
        phoenix_project_name=phoenix_project_name,
        phoenix_api_key=phoenix_api_key,
        phoenix_client_headers=phoenix_client_headers,
    )


def _init_tracing(config: OrchestratorConfig) -> Any:
    from phoenix.otel import register

    tracer_provider = register(
        endpoint=config.phoenix_collector_endpoint,
        project_name=config.phoenix_project_name,
        protocol="http/protobuf",
        batch=False,
        auto_instrument=True,
        headers=config.phoenix_client_headers or None,
        api_key=config.phoenix_api_key,
        verbose=True,
    )
    return tracer_provider


def _openrouter_client(config: OrchestratorConfig) -> Any:
    from openai import OpenAI

    default_headers: dict[str, str] = {}
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER") or None
    x_title = os.getenv("OPENROUTER_X_TITLE") or os.getenv("OPENROUTER_APP_TITLE") or "scm-cert-eval"
    if http_referer:
        default_headers["HTTP-Referer"] = http_referer
    if x_title:
        default_headers["X-Title"] = x_title

    return OpenAI(api_key=config.openrouter_api_key, base_url=config.openrouter_base_url, default_headers=default_headers)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _force_flush(tracer_provider: Any) -> None:
    for name in ("force_flush", "shutdown"):
        fn = getattr(tracer_provider, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass
            break


def _iter_tasks(all_tasks: dict[str, TaskRow], *, task_id: str | None, limit: int | None) -> list[TaskRow]:
    if task_id:
        if task_id not in all_tasks:
            raise RuntimeError(f"Unknown task_id: {task_id}")
        return [all_tasks[task_id]]

    rows = list(all_tasks.values())
    if limit is not None:
        rows = rows[:limit]
    return rows


def main(argv: list[str]) -> int:
    try:
        config = _load_config(argv)
    except Exception as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    tracer_provider = None
    try:
        tracer_provider = _init_tracing(config)
    except Exception as exc:
        print(f"TRACING INIT ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        import tools  # type: ignore
    except Exception as exc:
        print(f"IMPORT ERROR: {exc}", file=sys.stderr)
        return 2

    tool_schemas, name_to_callable, name_to_input_model = build_tool_registry(list(tools.ACTIVE_TOOLS))

    tasks = load_tasks(Path("data/benchmark/golden_tasks_questions_only.jsonl"))
    selected = _iter_tasks(tasks, task_id=config.task_id, limit=config.limit)

    client = _openrouter_client(config)

    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)

    failures = 0
    for task in selected:
        syntax_errors_caught_for_span: int | None = None
        raw_response = ""
        execution_metrics = {"syntax_errors_caught": 0, "successful_retry_attempt": 0, "tools_called": []}

        with tracer.start_as_current_span("scm.eval.task") as span:
            span.set_attribute("scm.eval.task_id", task.task_id)
            span.set_attribute("scm.eval.model_id", config.model_id)
            span.set_attribute("scm.eval.run_mode", config.run_mode)

            try:
                raw_response, metrics_obj = run_task(
                    task=task,
                    run_mode=config.run_mode,
                    model_id=config.model_id,
                    openai_client=client,
                    tool_schemas=tool_schemas,
                    name_to_callable=name_to_callable,
                    name_to_input_model=name_to_input_model,
                )
                execution_metrics = metrics_obj.to_json()
                syntax_errors_caught_for_span = int(execution_metrics["syntax_errors_caught"])
            except Exception as exc:
                failures += 1
                raw_response = ""
                execution_metrics = {"syntax_errors_caught": 0, "successful_retry_attempt": 0, "tools_called": []}
                span.set_attribute("scm.eval.error", f"{type(exc).__name__}: {exc}")
            finally:
                if syntax_errors_caught_for_span is not None:
                    span.set_attribute("scm.eval.syntax_errors_caught", syntax_errors_caught_for_span)
                else:
                    span.set_attribute("scm.eval.syntax_errors_caught", int(execution_metrics["syntax_errors_caught"]))

        row = {
            "task_id": task.task_id,
            "model_id": config.model_id,
            "run_mode": config.run_mode,
            "raw_response": raw_response,
            "execution_metrics": execution_metrics,
        }
        _append_jsonl(config.output_jsonl, row)

        _force_flush(tracer_provider)
        time.sleep(0.2)

        status = "OK" if raw_response else "ERR"
        print(f"{status} task_id={task.task_id} mode={config.run_mode} model={config.model_id}")

    if failures:
        print(f"Completed with {failures} failure(s). JSONL: {config.output_jsonl}", file=sys.stderr)
        return 1

    print(f"Completed {len(selected)} task(s). JSONL: {config.output_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
