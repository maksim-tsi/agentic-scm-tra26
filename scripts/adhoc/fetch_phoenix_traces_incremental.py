from __future__ import annotations

import argparse
import inspect
import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


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


def _extract_trace_id(obj: dict[str, Any]) -> str:
    for key in ("trace_id", "traceId", "id"):
        value = obj.get(key)
        if isinstance(value, str) and value:
            return value

    ctx = obj.get("context")
    if isinstance(ctx, dict):
        value = ctx.get("trace_id") or ctx.get("traceId")
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_start_dt(obj: dict[str, Any]) -> datetime | None:
    for key in ("start_time", "startTime", "start_time_iso", "startTimeISO"):
        value = obj.get(key)
        if isinstance(value, str):
            dt = _parse_iso_ts(value)
            if dt is not None:
                return dt
    for key in ("start_time_unix_nano", "startTimeUnixNano"):
        value = obj.get(key)
        if isinstance(value, int) and value > 0:
            return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
    return None


def _in_day(obj: dict[str, Any], day_start: datetime, day_end: datetime) -> bool:
    start_dt = _extract_start_dt(obj)
    if start_dt is None:
        return False
    return day_start <= start_dt <= day_end


def _candidate_base_urls() -> list[str]:
    urls: list[str] = []
    env_base = os.getenv("PHOENIX_BASE_URL")
    env_collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    if env_base:
        urls.append(env_base.rstrip("/"))
    if env_collector and env_collector.endswith("/v1/traces"):
        urls.append(env_collector[: -len("/v1/traces")].rstrip("/"))
    urls.extend(["http://127.0.0.1:6006", "http://192.168.107.172:6006"])

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def _preflight(url: str, timeout_s: float) -> tuple[bool, str]:
    try:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            response = client.get(url)
            snippet = response.text[:120].replace("\n", " ")
            return True, f"status={response.status_code} snippet={snippet!r}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _call_get_traces(client: Any, project: str, limit: int, day_start: datetime, day_end: datetime) -> list[dict[str, Any]]:
    fn = client.traces.get_traces
    sig = inspect.signature(fn)
    params = set(sig.parameters.keys())

    kwargs: dict[str, Any] = {"limit": limit}
    if "project_identifier" in params:
        kwargs["project_identifier"] = project
    elif "project_name" in params:
        kwargs["project_name"] = project
    elif "project" in params:
        kwargs["project"] = project

    if "include_spans" in params:
        kwargs["include_spans"] = True

    # Try to pass time window if supported by client version.
    for start_key in ("start_time", "from_time", "since"):
        if start_key in params:
            kwargs[start_key] = day_start
            break
    for end_key in ("end_time", "to_time", "until"):
        if end_key in params:
            kwargs[end_key] = day_end
            break

    rows = fn(**kwargs)
    if isinstance(rows, list):
        return [r for r in (_to_jsonable(x) for x in rows) if isinstance(r, dict)]

    collected: list[dict[str, Any]] = []
    for row in rows:
        j = _to_jsonable(row)
        if isinstance(j, dict):
            collected.append(j)
    return collected


def _call_get_spans(client: Any, project: str, limit: int, day_start: datetime, day_end: datetime) -> list[dict[str, Any]]:
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

    for start_key in ("start_time", "from_time", "since"):
        if start_key in params:
            kwargs[start_key] = day_start
            break
    for end_key in ("end_time", "to_time", "until"):
        if end_key in params:
            kwargs[end_key] = day_end
            break

    rows = fn(**kwargs)
    if isinstance(rows, list):
        return [r for r in (_to_jsonable(x) for x in rows) if isinstance(r, dict)]

    collected: list[dict[str, Any]] = []
    for row in rows:
        j = _to_jsonable(row)
        if isinstance(j, dict):
            collected.append(j)
    return collected


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _progress_line(label: str, current: int, total: int, *, width: int = 36) -> str:
    if total <= 0:
        pct = 100.0
        filled = width
    else:
        pct = (current / total) * 100.0
        filled = int((current / total) * width)
    bar = "#" * filled + "-" * (width - filled)
    return f"{label} [{bar}] {current}/{total} ({pct:5.1f}%)"


def _build_trace_from_spans(trace_id: str, spans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trace_id": trace_id,
        "spans": spans,
        "span_count": len(spans),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="List Phoenix trace IDs and fetch traces incrementally for one day.")
    parser.add_argument("--date", required=True, help="UTC day window YYYY-MM-DD")
    parser.add_argument("--project", default="agentic-scm-tra26", help="Phoenix project identifier")
    parser.add_argument("--base-url", default=None, help="Optional explicit Phoenix base URL")
    parser.add_argument("--limit", type=int, default=3000, help="Initial fetch limit")
    parser.add_argument(
        "--ids-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_ids.json"),
        help="Output JSON file with trace IDs",
    )
    parser.add_argument(
        "--append-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_incremental.jsonl"),
        help="JSONL file to append per-trace records",
    )
    parser.add_argument("--reset", action="store_true", help="Reset append file before writing")
    args = parser.parse_args()

    load_dotenv()

    target_day = date.fromisoformat(args.date)
    day_start = datetime.combine(target_day, time.min, tzinfo=UTC)
    day_end = datetime.combine(target_day, time.max, tzinfo=UTC)

    candidate_urls = [args.base_url.rstrip("/")] if args.base_url else _candidate_base_urls()
    chosen_url = ""
    preflight: list[dict[str, str]] = []
    for url in candidate_urls:
        ok, details = _preflight(url, timeout_s=3.0)
        preflight.append({"url": url, "ok": str(ok), "details": details})
        if ok and not chosen_url:
            chosen_url = url

    if not chosen_url:
        raise RuntimeError(f"No reachable Phoenix endpoint among: {candidate_urls}")

    from phoenix.client import Client

    client = Client(base_url=chosen_url)

    traces: list[dict[str, Any]] = []
    trace_source = "traces.get_traces"
    last_error = ""

    for limit in [args.limit, min(args.limit, 2000), min(args.limit, 1000), min(args.limit, 500)]:
        if limit <= 0:
            continue
        try:
            traces = _call_get_traces(client=client, project=args.project, limit=limit, day_start=day_start, day_end=day_end)
            break
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    spans_by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not traces:
        trace_source = "spans.get_spans_fallback"
        spans = _call_get_spans(client=client, project=args.project, limit=max(args.limit, 4000), day_start=day_start, day_end=day_end)
        for span in spans:
            trace_id = _extract_trace_id(span)
            if trace_id and _in_day(span, day_start, day_end):
                spans_by_trace[trace_id].append(span)

    trace_cache: dict[str, dict[str, Any]] = {}
    trace_ids: list[str] = []

    for tr in traces:
        trace_id = _extract_trace_id(tr)
        if not trace_id:
            continue
        # If API did not filter by day, enforce day filter locally from start time when possible.
        if _in_day(tr, day_start, day_end):
            trace_ids.append(trace_id)
            trace_cache[trace_id] = tr

    if not trace_ids and spans_by_trace:
        trace_ids = sorted(spans_by_trace.keys())

    trace_ids = sorted(set(trace_ids))

    ids_payload = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "project": args.project,
        "target_day_utc": args.date,
        "base_url": chosen_url,
        "source": trace_source,
        "trace_count": len(trace_ids),
        "trace_ids": trace_ids,
        "preflight": preflight,
        "trace_fetch_error_if_any": last_error,
    }
    args.ids_out.parent.mkdir(parents=True, exist_ok=True)
    args.ids_out.write_text(json.dumps(ids_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Scope milestone: 100% once list of trace IDs for project/day is produced.
    print(_progress_line("SCOPE IDENTIFIED", len(trace_ids), len(trace_ids)))

    if args.reset and args.append_out.exists():
        args.append_out.unlink()

    fetched = 0
    total_traces = len(trace_ids)
    print(_progress_line("FETCH+APPEND", 0, total_traces))
    for trace_id in trace_ids:
        status = "ok"
        source = "cache"
        payload: dict[str, Any] | None = None

        if trace_id in trace_cache:
            payload = trace_cache[trace_id]
        else:
            # Per-trace fetch attempts with best-effort compatibility.
            source = "per_trace_attempt"
            fetched_obj: dict[str, Any] | None = None
            errors: list[str] = []

            get_trace_fn = getattr(client.traces, "get_trace", None)
            if callable(get_trace_fn):
                try:
                    sig = inspect.signature(get_trace_fn)
                    params = set(sig.parameters.keys())
                    kwargs: dict[str, Any] = {}
                    if "trace_id" in params:
                        kwargs["trace_id"] = trace_id
                    elif "id" in params:
                        kwargs["id"] = trace_id

                    if "project_identifier" in params:
                        kwargs["project_identifier"] = args.project
                    elif "project_name" in params:
                        kwargs["project_name"] = args.project
                    elif "project" in params:
                        kwargs["project"] = args.project

                    one = get_trace_fn(**kwargs)
                    one_json = _to_jsonable(one)
                    if isinstance(one_json, dict):
                        fetched_obj = one_json
                except Exception as exc:
                    errors.append(f"get_trace failed: {type(exc).__name__}: {exc}")

            if fetched_obj is None:
                # Fallback: derive trace from previously fetched day spans.
                spans = spans_by_trace.get(trace_id, [])
                if spans:
                    source = "spans_filtered"
                    fetched_obj = _build_trace_from_spans(trace_id=trace_id, spans=spans)
                else:
                    status = "missing"
                    source = "unavailable"
                    fetched_obj = {"trace_id": trace_id, "errors": errors}

            payload = fetched_obj

        row = {
            "fetched_at_utc": datetime.now(tz=UTC).isoformat(),
            "project": args.project,
            "target_day_utc": args.date,
            "base_url": chosen_url,
            "trace_id": trace_id,
            "status": status,
            "source": source,
            "trace": payload,
        }
        _append_jsonl(args.append_out, row)
        fetched += 1
        print(_progress_line("FETCH+APPEND", fetched, total_traces))

    print(f"Chosen Phoenix endpoint: {chosen_url}")
    print(f"Project: {args.project}")
    print(f"Target day (UTC): {args.date}")
    print(f"Trace IDs listed: {len(trace_ids)}")
    print(f"IDs file: {args.ids_out}")
    print(f"Incremental append file: {args.append_out}")
    print(f"Trace rows appended this run: {fetched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())