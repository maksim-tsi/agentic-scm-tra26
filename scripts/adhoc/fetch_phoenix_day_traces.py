from __future__ import annotations

import argparse
import inspect
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


def _safe_text(value: Any, *, max_len: int = 5000) -> str:
    try:
        text = str(value)
    except Exception:
        return ""
    if len(text) > max_len:
        return text[:max_len]
    return text


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]

    for attr in ("model_dump", "dict", "to_dict"):
        fn = getattr(value, attr, None)
        if callable(fn):
            try:
                return _to_jsonable(fn())
            except Exception:
                pass

    if hasattr(value, "__dict__"):
        try:
            return _to_jsonable(vars(value))
        except Exception:
            pass

    return str(value)


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


def _extract_attr_map(span: dict[str, Any]) -> dict[str, Any]:
    attrs = span.get("attributes")
    if isinstance(attrs, dict):
        return attrs
    return {}


def _extract_trace_id(span: dict[str, Any]) -> str:
    for key in ("trace_id", "traceId"):
        val = span.get(key)
        if isinstance(val, str) and val:
            return val

    ctx = span.get("context")
    if isinstance(ctx, dict):
        val = ctx.get("trace_id") or ctx.get("traceId")
        if isinstance(val, str) and val:
            return val

    return ""


def _extract_span_name(span: dict[str, Any]) -> str:
    for key in ("name", "span_name", "spanName"):
        val = span.get(key)
        if isinstance(val, str) and val:
            return val
    return "<unknown>"


def _extract_span_start(span: dict[str, Any]) -> datetime | None:
    for key in ("start_time", "startTime", "start_time_iso", "startTimeISO"):
        val = span.get(key)
        if isinstance(val, str):
            dt = _parse_iso_ts(val)
            if dt is not None:
                return dt

    for key in ("start_time_unix_nano", "startTimeUnixNano"):
        val = span.get(key)
        if isinstance(val, int) and val > 0:
            return datetime.fromtimestamp(val / 1_000_000_000, tz=UTC)

    return None


def _extract_span_end(span: dict[str, Any]) -> datetime | None:
    for key in ("end_time", "endTime", "end_time_iso", "endTimeISO"):
        val = span.get(key)
        if isinstance(val, str):
            dt = _parse_iso_ts(val)
            if dt is not None:
                return dt

    for key in ("end_time_unix_nano", "endTimeUnixNano"):
        val = span.get(key)
        if isinstance(val, int) and val > 0:
            return datetime.fromtimestamp(val / 1_000_000_000, tz=UTC)

    return None


def _candidate_base_urls() -> list[str]:
    urls: list[str] = []
    env_base = os.getenv("PHOENIX_BASE_URL")
    env_collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")

    if env_base:
        urls.append(env_base.rstrip("/"))
    if env_collector and env_collector.endswith("/v1/traces"):
        urls.append(env_collector[: -len("/v1/traces")].rstrip("/"))

    urls.extend(["http://127.0.0.1:6006", "http://192.168.107.172:6006"])

    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _preflight_http(url: str, timeout_s: float) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            response = client.get(url)
            snippet = response.text[:120].replace("\n", " ")
            return True, f"status={response.status_code} body_snippet={snippet!r}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _call_get_spans(
    client: Any,
    project: str,
    limit: int,
    day_start_utc: datetime,
    day_end_utc: datetime,
) -> list[dict[str, Any]]:
    fn = client.spans.get_spans
    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs: dict[str, Any] = {"limit": limit}
    if "project_identifier" in params:
        kwargs["project_identifier"] = project
    elif "project_name" in params:
        kwargs["project_name"] = project
    elif "project" in params:
        kwargs["project"] = project

    if "start_time" in params:
        kwargs["start_time"] = day_start_utc.isoformat()
    if "end_time" in params:
        kwargs["end_time"] = day_end_utc.isoformat()

    if "from_time" in params:
        kwargs["from_time"] = day_start_utc.isoformat()
    if "to_time" in params:
        kwargs["to_time"] = day_end_utc.isoformat()

    rows = fn(**kwargs)
    if isinstance(rows, list):
        return [r for r in (_to_jsonable(x) for x in rows) if isinstance(r, dict)]

    collected: list[dict[str, Any]] = []
    for item in rows:
        j = _to_jsonable(item)
        if isinstance(j, dict):
            collected.append(j)
    return collected


@dataclass(frozen=True)
class TraceSummary:
    trace_id: str
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


def _normalize_traces(spans: list[dict[str, Any]], target_day: date) -> tuple[list[dict[str, Any]], list[TraceSummary]]:
    day_start = datetime.combine(target_day, time.min, tzinfo=UTC)
    day_end = datetime.combine(target_day, time.max, tzinfo=UTC)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    filtered_spans: list[dict[str, Any]] = []

    for span in spans:
        trace_id = _extract_trace_id(span)
        if not trace_id:
            continue

        start_dt = _extract_span_start(span)
        end_dt = _extract_span_end(span)
        in_day = False
        if start_dt is not None and day_start <= start_dt <= day_end:
            in_day = True
        elif end_dt is not None and day_start <= end_dt <= day_end:
            in_day = True

        if not in_day:
            continue

        grouped[trace_id].append(span)
        filtered_spans.append(span)

    summaries: list[TraceSummary] = []
    for trace_id, trace_spans in grouped.items():
        starts = [dt for dt in (_extract_span_start(s) for s in trace_spans) if dt is not None]
        ends = [dt for dt in (_extract_span_end(s) for s in trace_spans) if dt is not None]
        attrs_list = [_extract_attr_map(s) for s in trace_spans]

        task_ids: set[str] = set()
        model_ids: set[str] = set()
        run_modes: set[str] = set()
        span_names: Counter[str] = Counter()
        tool_hits = 0
        yaam_hits = 0
        error_hits = 0

        for span, attrs in zip(trace_spans, attrs_list):
            span_names[_extract_span_name(span)] += 1

            task = attrs.get("scm.eval.task_id")
            model = attrs.get("scm.eval.model_id")
            mode = attrs.get("scm.eval.run_mode")
            if isinstance(task, str) and task:
                task_ids.add(task)
            if isinstance(model, str) and model:
                model_ids.add(model)
            if isinstance(mode, str) and mode:
                run_modes.add(mode)

            low = _safe_text({"name": _extract_span_name(span), "attrs": attrs}).lower()
            if "tool" in low or "executor_tools" in low or "tools_called" in low:
                tool_hits += 1
            if "yaam" in low or "/v2/memory/l" in low or "retrieved_context" in low:
                yaam_hits += 1
            if "error" in low or "exception" in low or "validation" in low or "recursion" in low:
                error_hits += 1

        summaries.append(
            TraceSummary(
                trace_id=trace_id,
                span_count=len(trace_spans),
                start_utc=min(starts).isoformat() if starts else None,
                end_utc=max(ends).isoformat() if ends else None,
                task_ids=sorted(task_ids),
                model_ids=sorted(model_ids),
                run_modes=sorted(run_modes),
                top_span_names=span_names.most_common(10),
                tool_signal_hits=tool_hits,
                yaam_signal_hits=yaam_hits,
                error_signal_hits=error_hits,
            )
        )

    summaries.sort(key=lambda s: (s.start_utc or "", s.trace_id))
    return filtered_spans, summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and normalize Phoenix traces for a single UTC day.")
    parser.add_argument("--date", required=True, help="Day in YYYY-MM-DD (UTC day window).")
    parser.add_argument("--project", default="agentic-scm-tra26", help="Phoenix project identifier.")
    parser.add_argument("--base-url", default=None, help="Optional Phoenix base URL override.")
    parser.add_argument("--limit", type=int, default=10000, help="Span fetch limit for client call.")
    parser.add_argument(
        "--raw-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_raw.json"),
        help="Path for raw trace-span payload.",
    )
    parser.add_argument(
        "--normalized-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_normalized.json"),
        help="Path for normalized trace summaries.",
    )
    parser.add_argument(
        "--per-trace-dir",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_traces"),
        help="Directory for one JSON file per trace.",
    )
    args = parser.parse_args()

    load_dotenv()

    target_day = date.fromisoformat(args.date)
    day_start = datetime.combine(target_day, time.min, tzinfo=UTC)
    day_end = datetime.combine(target_day, time.max, tzinfo=UTC)
    candidate_urls = [args.base_url.rstrip("/")] if args.base_url else _candidate_base_urls()

    preflight_results: list[dict[str, str]] = []
    chosen_url = ""
    for url in candidate_urls:
        ok, details = _preflight_http(url, timeout_s=3.0)
        preflight_results.append({"url": url, "ok": str(ok), "details": details})
        if ok and not chosen_url:
            chosen_url = url

    if not chosen_url:
        raise RuntimeError(f"No reachable Phoenix endpoint from candidates: {candidate_urls}")

    try:
        from phoenix.client import Client
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"phoenix client import failed: {type(exc).__name__}: {exc}") from exc

    client = Client(base_url=chosen_url)
    spans: list[dict[str, Any]] = []
    limit_candidates = [args.limit, min(args.limit, 3000), min(args.limit, 1500), min(args.limit, 800)]
    used_limit = 0
    last_exc: Exception | None = None

    for candidate in limit_candidates:
        if candidate <= 0:
            continue
        try:
            spans = _call_get_spans(
                client=client,
                project=args.project,
                limit=candidate,
                day_start_utc=day_start,
                day_end_utc=day_end,
            )
            used_limit = candidate
            break
        except Exception as exc:
            last_exc = exc
            continue

    if not spans and last_exc is not None:
        raise RuntimeError(f"Phoenix get_spans failed after retries: {type(last_exc).__name__}: {last_exc}")

    filtered_spans, summaries = _normalize_traces(spans=spans, target_day=target_day)

    args.raw_out.parent.mkdir(parents=True, exist_ok=True)
    args.per_trace_dir.mkdir(parents=True, exist_ok=True)

    raw_payload = {
        "fetched_at_utc": datetime.now(tz=UTC).isoformat(),
        "project": args.project,
        "target_day_utc": args.date,
        "base_url": chosen_url,
        "fetch_method": "phoenix.client.Client.spans.get_spans",
        "fetch_limit_requested": args.limit,
        "fetch_limit_used": used_limit,
        "preflight": preflight_results,
        "spans_returned": len(spans),
        "spans_in_target_day": len(filtered_spans),
        "spans": filtered_spans,
    }
    args.raw_out.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    normalized_payload = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "project": args.project,
        "target_day_utc": args.date,
        "base_url": chosen_url,
        "trace_count": len(summaries),
        "traces": [
            {
                "trace_id": s.trace_id,
                "span_count": s.span_count,
                "start_utc": s.start_utc,
                "end_utc": s.end_utc,
                "task_ids": s.task_ids,
                "model_ids": s.model_ids,
                "run_modes": s.run_modes,
                "top_span_names": s.top_span_names,
                "tool_signal_hits": s.tool_signal_hits,
                "yaam_signal_hits": s.yaam_signal_hits,
                "error_signal_hits": s.error_signal_hits,
            }
            for s in summaries
        ],
    }
    args.normalized_out.parent.mkdir(parents=True, exist_ok=True)
    args.normalized_out.write_text(json.dumps(normalized_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    grouped_for_files: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for span in filtered_spans:
        trace_id = _extract_trace_id(span)
        if trace_id:
            grouped_for_files[trace_id].append(span)

    for summary in summaries:
        path = args.per_trace_dir / f"{summary.trace_id}.json"
        payload = {
            "trace_summary": {
                "trace_id": summary.trace_id,
                "span_count": summary.span_count,
                "start_utc": summary.start_utc,
                "end_utc": summary.end_utc,
                "task_ids": summary.task_ids,
                "model_ids": summary.model_ids,
                "run_modes": summary.run_modes,
                "top_span_names": summary.top_span_names,
                "tool_signal_hits": summary.tool_signal_hits,
                "yaam_signal_hits": summary.yaam_signal_hits,
                "error_signal_hits": summary.error_signal_hits,
            },
            "spans": grouped_for_files.get(summary.trace_id, []),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Phoenix endpoint: {chosen_url}")
    print(f"Project: {args.project}")
    print(f"Target day (UTC): {args.date}")
    print(f"Returned spans: {len(spans)}")
    print(f"Filtered spans in target day: {len(filtered_spans)}")
    print(f"Trace count in target day: {len(summaries)}")
    print(f"Raw output: {args.raw_out}")
    print(f"Normalized output: {args.normalized_out}")
    print(f"Per-trace directory: {args.per_trace_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())