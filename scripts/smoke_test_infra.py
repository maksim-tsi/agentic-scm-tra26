from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from dotenv import load_dotenv


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_MODELS = [
    "x-ai/grok-4.1-fast",
    "meta-llama/llama-3.1-8b-instruct",
    "deepseek/deepseek-v3.2",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]

PROMPT = "Respond with exactly the text 'SCM-INFRA-OK' and nothing else."
EXPECTED = "SCM-INFRA-OK"

PARENT_SPAN_NAME = "scm.infra_smoke_test"
RUN_MODE = "Naive"


@dataclass(frozen=True)
class SmokeConfig:
    task_id: str
    project_name: str
    models: list[str]
    openrouter_base_url: str
    openrouter_api_key: str
    phoenix_collector_endpoint: str
    phoenix_base_url: str
    phoenix_api_key: str | None
    phoenix_client_headers: dict[str, str]
    timeout_s: float


def _parse_header_kv_pairs(raw: str) -> dict[str, str]:
    """
    Parse PHOENIX_CLIENT_HEADERS-like strings.

    Supported:
    - "k=v"
    - "k=v,foo=bar"
    """
    headers: dict[str, str] = {}
    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value
    return headers


def _substitute_env_vars(template: str) -> str:
    # Minimal substitution for patterns found in our .env.example.
    # python-dotenv typically handles interpolation, but we keep this as a safe fallback.
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
        resolved = _substitute_env_vars(raw)
        return resolved

    dev_node_ip = os.getenv("DEV_NODE_IP")
    if not dev_node_ip:
        raise RuntimeError("Missing required env var: DEV_NODE_IP (needed to build PHOENIX_COLLECTOR_ENDPOINT)")

    phoenix_port = os.getenv("PHOENIX_PORT") or "6006"
    return f"http://{dev_node_ip}:{phoenix_port}/v1/traces"


def _resolve_phoenix_base_url(collector_endpoint: str) -> str:
    raw = os.getenv("PHOENIX_BASE_URL") or ""
    if raw:
        return _substitute_env_vars(raw)

    if collector_endpoint.endswith("/v1/traces"):
        return collector_endpoint[: -len("/v1/traces")]

    dev_node_ip = os.getenv("DEV_NODE_IP")
    if not dev_node_ip:
        raise RuntimeError("Missing required env var: DEV_NODE_IP (needed to build PHOENIX_BASE_URL)")

    phoenix_port = os.getenv("PHOENIX_PORT") or "6006"
    return f"http://{dev_node_ip}:{phoenix_port}"


def _load_config(argv: list[str]) -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Infra smoke test: OpenRouter + Phoenix tracing validation.")
    parser.add_argument("--model", action="append", default=None, help="OpenRouter model identifier (repeatable).")
    parser.add_argument("--task-id", default="smoke_test_001", help="Task identifier for trace filtering.")
    parser.add_argument(
        "--project",
        default=None,
        help="Phoenix project identifier (default: PHOENIX_PROJECT_NAME or scm-cert-eval-sandbox).",
    )
    parser.add_argument("--timeout-s", type=float, default=60.0, help="Timeout for Phoenix polling per model.")
    args = parser.parse_args(argv)

    load_dotenv()

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
    if not openrouter_api_key:
        raise RuntimeError("Missing required env var: OPENROUTER_API_KEY")

    openrouter_base_url = os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL

    collector_endpoint = _resolve_phoenix_collector_endpoint()
    phoenix_base_url = _resolve_phoenix_base_url(collector_endpoint)

    project_name = args.project or os.getenv("PHOENIX_PROJECT_NAME") or "scm-cert-eval-sandbox"

    phoenix_api_key = os.getenv("PHOENIX_API_KEY") or None
    phoenix_client_headers_raw = os.getenv("PHOENIX_CLIENT_HEADERS") or ""
    phoenix_client_headers = _parse_header_kv_pairs(phoenix_client_headers_raw)
    if phoenix_api_key and "Authorization" not in phoenix_client_headers:
        phoenix_client_headers["Authorization"] = f"Bearer {phoenix_api_key}"

    models = args.model if args.model else DEFAULT_MODELS
    models = [m.strip() for m in models if m and m.strip()]
    if not models:
        raise RuntimeError("No models provided (and default model list is empty).")

    return SmokeConfig(
        task_id=args.task_id,
        project_name=project_name,
        models=models,
        openrouter_base_url=openrouter_base_url,
        openrouter_api_key=openrouter_api_key,
        phoenix_collector_endpoint=collector_endpoint,
        phoenix_base_url=phoenix_base_url,
        phoenix_api_key=phoenix_api_key,
        phoenix_client_headers=phoenix_client_headers,
        timeout_s=args.timeout_s,
    )


def _init_tracing(config: SmokeConfig):
    try:
        from phoenix.otel import register
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: arize-phoenix-otel. Install with: uv sync --dev --frozen"
        ) from exc

    tracer_provider = register(
        endpoint=config.phoenix_collector_endpoint,
        project_name=config.project_name,
        protocol="http/protobuf",
        batch=False,
        auto_instrument=True,
        headers=config.phoenix_client_headers or None,
        api_key=config.phoenix_api_key,
        verbose=True,
    )
    return tracer_provider


def _openrouter_client(config: SmokeConfig):
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("Missing dependency: openai. Install with: uv sync --dev --frozen") from exc

    default_headers: dict[str, str] = {}
    http_referer = os.getenv("OPENROUTER_HTTP_REFERER") or None
    x_title = os.getenv("OPENROUTER_X_TITLE") or os.getenv("OPENROUTER_APP_TITLE") or "scm-cert-eval"
    if http_referer:
        default_headers["HTTP-Referer"] = http_referer
    if x_title:
        default_headers["X-Title"] = x_title

    return OpenAI(api_key=config.openrouter_api_key, base_url=config.openrouter_base_url, default_headers=default_headers)


def _require_exact_response(content: str, *, model: str) -> None:
    if content.strip() != EXPECTED:
        raise RuntimeError(f"Model {model} returned unexpected content: {content!r}")


def _force_flush(tracer_provider: Any) -> None:
    # phoenix.otel.register returns an OpenTelemetry TracerProvider wrapper.
    # It should expose force_flush(), but we keep this defensive.
    for name in ("force_flush", "shutdown"):
        fn = getattr(tracer_provider, name, None)
        if callable(fn):
            try:
                fn()
            except Exception:
                # Best-effort flush; Phoenix polling is the ultimate validation.
                pass
            break


def _span_attr(span: Any, key: str) -> Any:
    attrs = getattr(span, "attributes", None)
    if isinstance(attrs, dict):
        return attrs.get(key)
    return None


def _span_trace_id(span: Any) -> str | None:
    ctx = getattr(span, "context", None)
    trace_id = getattr(ctx, "trace_id", None)
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    return None


def _span_output_contains_expected(span: Any) -> bool:
    attrs = getattr(span, "attributes", None)
    if not isinstance(attrs, dict):
        return False

    for key, value in attrs.items():
        if not isinstance(key, str):
            continue
        if "output" not in key.lower() and "response" not in key.lower() and "completion" not in key.lower():
            continue
        if isinstance(value, str) and EXPECTED in value:
            return True
        if isinstance(value, (list, dict)):
            try:
                rendered = str(value)
            except Exception:
                continue
            if EXPECTED in rendered:
                return True

    return False


def _poll_for_trace(
    *,
    config: SmokeConfig,
    model: str,
    start_time: datetime,
    timeout_s: float,
) -> None:
    try:
        from phoenix.client import Client
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "Missing dependency: arize-phoenix-client. Install with: uv sync --dev --frozen"
        ) from exc

    client = Client(base_url=config.phoenix_base_url, api_key=config.phoenix_api_key, headers=config.phoenix_client_headers)

    deadline = time.time() + timeout_s
    last_seen_count = 0

    while time.time() < deadline:
        try:
            spans = client.spans.get_spans(
                project_identifier=config.project_name,
                start_time=start_time,
                limit=500,
                timeout=10,
            )
        except Exception as exc:
            # Phoenix can be temporarily unavailable during startup; keep polling.
            last_seen_count = 0
            time.sleep(1.0)
            continue

        last_seen_count = len(spans)

        parent_span = None
        for span in spans:
            if getattr(span, "name", None) != PARENT_SPAN_NAME:
                continue
            if _span_attr(span, "scm.eval.task_id") != config.task_id:
                continue
            if _span_attr(span, "scm.eval.model_id") != model:
                continue
            if _span_attr(span, "scm.eval.run_mode") != RUN_MODE:
                continue
            parent_span = span
            break

        if not parent_span:
            time.sleep(1.0)
            continue

        trace_id = _span_trace_id(parent_span)
        if not trace_id:
            time.sleep(1.0)
            continue

        for span in spans:
            if _span_trace_id(span) != trace_id:
                continue
            if _span_output_contains_expected(span):
                return

        time.sleep(1.0)

    raise RuntimeError(
        "Phoenix validation timed out: missing parent/child span match "
        f"(project={config.project_name!r}, task_id={config.task_id!r}, model={model!r}, "
        f"phoenix_base_url={config.phoenix_base_url!r}, spans_seen_last_poll={last_seen_count})"
    )


def _run_for_model(config: SmokeConfig, *, tracer_provider: Any, model: str) -> None:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
    client = _openrouter_client(config)

    start_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    with tracer.start_as_current_span(PARENT_SPAN_NAME) as span:
        span.set_attribute("scm.eval.task_id", config.task_id)
        span.set_attribute("scm.eval.run_mode", RUN_MODE)
        span.set_attribute("scm.eval.model_id", model)

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=0,
            max_tokens=16,
        )
        content = resp.choices[0].message.content or ""

        _require_exact_response(content, model=model)

    _force_flush(tracer_provider)
    time.sleep(3.0)
    _poll_for_trace(config=config, model=model, start_time=start_time, timeout_s=config.timeout_s)


def main(argv: list[str]) -> int:
    try:
        config = _load_config(argv)
    except Exception as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        tracer_provider = _init_tracing(config)
    except Exception as exc:
        print(f"TRACING INIT ERROR: {exc}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for model in config.models:
        try:
            _run_for_model(config, tracer_provider=tracer_provider, model=model)
        except Exception as exc:
            failures.append(model)
            print(f"FAIL {model}: {exc}", file=sys.stderr)
        else:
            print(f"PASS {model}")

    if failures:
        print(f"Smoke test failed for {len(failures)} model(s): {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

