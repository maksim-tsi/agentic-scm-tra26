from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_iso_ts(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _extract_trace_id(span: dict[str, Any]) -> str:
    for key in ("trace_id", "traceId"):
        value = span.get(key)
        if isinstance(value, str) and value:
            return value
    ctx = span.get("context")
    if isinstance(ctx, dict):
        for key in ("trace_id", "traceId"):
            value = ctx.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _extract_start_dt(span: dict[str, Any]) -> datetime | None:
    for key in ("start_time", "startTime", "start_time_iso", "startTimeISO"):
        value = span.get(key)
        if isinstance(value, str):
            dt = _parse_iso_ts(value)
            if dt is not None:
                return dt
    for key in ("start_time_unix_nano", "startTimeUnixNano"):
        value = span.get(key)
        if isinstance(value, int) and value > 0:
            return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
    return None


def _extract_end_dt(span: dict[str, Any]) -> datetime | None:
    for key in ("end_time", "endTime", "end_time_iso", "endTimeISO"):
        value = span.get(key)
        if isinstance(value, str):
            dt = _parse_iso_ts(value)
            if dt is not None:
                return dt
    for key in ("end_time_unix_nano", "endTimeUnixNano"):
        value = span.get(key)
        if isinstance(value, int) and value > 0:
            return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
    return None


def _extract_attrs(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span.get("attributes")
    if isinstance(attrs, dict):
        return attrs
    return {}


def _extract_span_name(span: dict[str, Any]) -> str:
    for key in ("name", "span_name", "spanName"):
        value = span.get(key)
        if isinstance(value, str) and value:
            return value
    return "<unknown>"


def _classify_error_signatures(text: str) -> list[str]:
    low = text.lower()
    categories: list[str] = []
    if "pydantic" in low or "validation errors for" in low:
        categories.append("pydantic_validation")
    if "json invalid" in low or "invalid json" in low or "expected value at line" in low:
        categories.append("json_structure")
    if "429" in low or "rate limit" in low:
        categories.append("rate_limit_429")
    if "openrouter" in low or "api" in low or "provider" in low or "status code" in low:
        categories.append("provider_api")
    if "timeout" in low or "timed out" in low or "readtimeout" in low:
        categories.append("timeout")
    if "recursion" in low or "graphrecursionerror" in low:
        categories.append("recursion")
    return categories


@dataclass(frozen=True)
class CompactRow:
    trace_id: str
    status: str
    source: str
    span_count: int
    start_utc: str | None
    end_utc: str | None
    task_ids: list[str]
    model_ids: list[str]
    run_modes: list[str]
    top_span_names: list[tuple[str, int]]
    tool_signal_hits: int
    yaam_signal_hits: int
    error_signal_hits: int
    error_categories: list[tuple[str, int]]


def _compact_record(row: dict[str, Any]) -> CompactRow | None:
    trace = row.get("trace")
    if not isinstance(trace, dict):
        return None

    trace_id = row.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        fallback = trace.get("trace_id")
        if isinstance(fallback, str) and fallback:
            trace_id = fallback
        else:
            spans0 = trace.get("spans")
            if isinstance(spans0, list) and spans0 and isinstance(spans0[0], dict):
                trace_id = _extract_trace_id(spans0[0])

    if not isinstance(trace_id, str) or not trace_id:
        return None

    spans = trace.get("spans")
    if not isinstance(spans, list):
        spans = []

    starts: list[datetime] = []
    ends: list[datetime] = []
    task_ids: set[str] = set()
    model_ids: set[str] = set()
    run_modes: set[str] = set()
    span_names: Counter[str] = Counter()
    error_cats: Counter[str] = Counter()

    tool_hits = 0
    yaam_hits = 0
    err_hits = 0

    for span in spans:
        if not isinstance(span, dict):
            continue

        start_dt = _extract_start_dt(span)
        end_dt = _extract_end_dt(span)
        if start_dt is not None:
            starts.append(start_dt)
        if end_dt is not None:
            ends.append(end_dt)

        name = _extract_span_name(span)
        span_names[name] += 1
        attrs = _extract_attrs(span)

        task = attrs.get("scm.eval.task_id")
        model = attrs.get("scm.eval.model_id")
        mode = attrs.get("scm.eval.run_mode")
        if isinstance(task, str) and task:
            task_ids.add(task)
        if isinstance(model, str) and model:
            model_ids.add(model)
        if isinstance(mode, str) and mode:
            run_modes.add(mode)

        evidence_text = json.dumps({"name": name, "attrs": attrs}, ensure_ascii=False)
        low = evidence_text.lower()
        if "tool" in low or "executor_tools" in low or "tools_called" in low:
            tool_hits += 1
        if "yaam" in low or "/v2/memory/l" in low or "retrieved_context" in low:
            yaam_hits += 1
        if "error" in low or "exception" in low or "validation" in low or "recursion" in low:
            err_hits += 1
        for cat in _classify_error_signatures(low):
            error_cats[cat] += 1

    return CompactRow(
        trace_id=trace_id,
        status=str(row.get("status") or "unknown"),
        source=str(row.get("source") or "unknown"),
        span_count=len(spans),
        start_utc=min(starts).isoformat() if starts else None,
        end_utc=max(ends).isoformat() if ends else None,
        task_ids=sorted(task_ids),
        model_ids=sorted(model_ids),
        run_modes=sorted(run_modes),
        top_span_names=span_names.most_common(8),
        tool_signal_hits=tool_hits,
        yaam_signal_hits=yaam_hits,
        error_signal_hits=err_hits,
        error_categories=error_cats.most_common(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact large Phoenix trace logs into analysis-ready summaries.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_analyst_raw.jsonl"),
        help="Input raw per-trace JSONL file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_compact.jsonl"),
        help="Compact output JSONL path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_compact_summary.json"),
        help="Summary JSON path.",
    )
    parser.add_argument("--reset", action="store_true", help="Reset output files before writing.")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input not found: {args.input}")

    if args.reset:
        if args.output.exists():
            args.output.unlink()
        if args.summary.exists():
            args.summary.unlink()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    total_rows = 0
    compacted_rows = 0
    parse_fail_rows = 0
    global_errors: Counter[str] = Counter()
    global_models: Counter[str] = Counter()
    global_run_modes: Counter[str] = Counter()

    with args.input.open("r", encoding="utf-8") as src, args.output.open("a", encoding="utf-8") as out:
        for raw in src:
            line = raw.strip()
            if not line:
                continue
            total_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                parse_fail_rows += 1
                continue

            if not isinstance(row, dict):
                parse_fail_rows += 1
                continue

            compact = _compact_record(row)
            if compact is None:
                parse_fail_rows += 1
                continue

            compacted_rows += 1
            for model in compact.model_ids:
                global_models[model] += 1
            for mode in compact.run_modes:
                global_run_modes[mode] += 1
            for name, count in compact.error_categories:
                global_errors[name] += count

            out_row = {
                "trace_id": compact.trace_id,
                "status": compact.status,
                "source": compact.source,
                "span_count": compact.span_count,
                "start_utc": compact.start_utc,
                "end_utc": compact.end_utc,
                "task_ids": compact.task_ids,
                "model_ids": compact.model_ids,
                "run_modes": compact.run_modes,
                "top_span_names": compact.top_span_names,
                "tool_signal_hits": compact.tool_signal_hits,
                "yaam_signal_hits": compact.yaam_signal_hits,
                "error_signal_hits": compact.error_signal_hits,
                "error_categories": compact.error_categories,
            }
            out.write(json.dumps(out_row, ensure_ascii=False) + "\n")

    summary = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "input": str(args.input),
        "output": str(args.output),
        "total_rows": total_rows,
        "compacted_rows": compacted_rows,
        "parse_fail_rows": parse_fail_rows,
        "error_categories": global_errors.most_common(),
        "model_ids": global_models.most_common(),
        "run_modes": global_run_modes.most_common(),
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Input rows: {total_rows}")
    print(f"Compacted rows: {compacted_rows}")
    print(f"Parse/compact failures: {parse_fail_rows}")
    print(f"Compact file: {args.output}")
    print(f"Summary file: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())