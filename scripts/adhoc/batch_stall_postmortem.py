from __future__ import annotations

import argparse
import json
import math
import pickle
import sqlite3
import statistics
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None


@dataclass
class TaskCheckpointStats:
    task_id: str
    thread_id: str
    checkpoint_count: int
    step_min: int | None
    step_max: int | None
    step_unique_count: int
    source_counts: dict[str, int]
    channel_counts: dict[str, int]
    validation_error_hits: int
    timeout_hits: int
    rate_limit_hits: int
    last_checkpoint_id: str | None
    last_parent_checkpoint_id: str | None
    last_metadata: dict[str, Any]
    suspected_issue: str
    max_rowid: int


@dataclass
class PhoenixLatency:
    task_id: str
    count: int
    mean_ms: float
    p50_ms: float
    p95_ms: float


def _safe_text(value: Any, *, max_len: int = 5000) -> str:
    try:
        text = str(value)
    except Exception:
        return ""
    if len(text) > max_len:
        return text[:max_len]
    return text


def _decode_blob(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, memoryview):
        value = value.tobytes()

    if isinstance(value, (dict, list, str, int, float, bool)):
        return value

    if not isinstance(value, (bytes, bytearray)):
        return value

    raw = bytes(value)
    variants = [raw]
    try:
        variants.insert(0, zlib.decompress(raw))
    except Exception:
        pass

    for blob in variants:
        if msgpack is not None:
            try:
                return msgpack.unpackb(blob, raw=False)
            except Exception:
                pass

        try:
            return json.loads(blob.decode("utf-8"))
        except Exception:
            pass

        try:
            return pickle.loads(blob)
        except Exception:
            pass

    return raw


def _load_dataset_task_ids(dataset_path: Path) -> list[str]:
    task_ids: list[str] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            task_id = row.get("task_id") if isinstance(row, dict) else None
            if isinstance(task_id, str) and task_id:
                task_ids.append(task_id)
    return task_ids


def _build_thread_parser(task_ids: list[str]):
    ordered = sorted(task_ids, key=len, reverse=True)

    def _parse(thread_id: str) -> str | None:
        for task_id in ordered:
            if thread_id.startswith(f"{task_id}_"):
                return task_id
        return None

    return _parse


def _select_recent_task_threads(
    conn: sqlite3.Connection,
    *,
    dataset_task_ids: list[str],
    task_limit: int,
) -> list[tuple[str, str, int]]:
    parse_task = _build_thread_parser(dataset_task_ids)
    seen_tasks: set[str] = set()
    selected_desc: list[tuple[str, str, int]] = []

    cursor = conn.execute("SELECT rowid, thread_id FROM checkpoints ORDER BY rowid DESC")
    for rowid, thread_id in cursor:
        if not isinstance(thread_id, str):
            continue
        task_id = parse_task(thread_id)
        if not task_id or task_id in seen_tasks:
            continue

        seen_tasks.add(task_id)
        selected_desc.append((task_id, thread_id, int(rowid)))
        if len(selected_desc) >= task_limit:
            break

    # Return oldest -> newest attempted order for easier trend analysis.
    return list(reversed(selected_desc))


def _collect_write_channel_counts(conn: sqlite3.Connection, thread_id: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    cursor = conn.execute(
        "SELECT channel, COUNT(*) FROM writes WHERE thread_id=? GROUP BY channel",
        (thread_id,),
    )
    for channel, n in cursor:
        key = channel if isinstance(channel, str) else "<none>"
        counts[key] += int(n)
    return dict(counts)


def _scan_write_text_for_signals(conn: sqlite3.Connection, thread_id: str) -> tuple[int, int, int]:
    validation_hits = 0
    timeout_hits = 0
    rate_limit_hits = 0

    cursor = conn.execute("SELECT value FROM writes WHERE thread_id=?", (thread_id,))
    for (raw_value,) in cursor:
        decoded = _decode_blob(raw_value)
        text = _safe_text(decoded).lower()
        if not text:
            continue

        if "validationerror" in text or "pydantic" in text:
            validation_hits += 1
        if "timeout" in text or "timed out" in text:
            timeout_hits += 1
        if "rate limit" in text or "429" in text:
            rate_limit_hits += 1

    return validation_hits, timeout_hits, rate_limit_hits


def _analyze_task_thread(conn: sqlite3.Connection, task_id: str, thread_id: str) -> TaskCheckpointStats:
    row_cursor = conn.execute(
        """
        SELECT rowid, checkpoint_id, parent_checkpoint_id, metadata
        FROM checkpoints
        WHERE thread_id=?
        ORDER BY rowid ASC
        """,
        (thread_id,),
    )

    rowids: list[int] = []
    steps: list[int] = []
    source_counts: Counter[str] = Counter()
    last_checkpoint_id: str | None = None
    last_parent_checkpoint_id: str | None = None
    last_metadata: dict[str, Any] = {}

    for rowid, checkpoint_id, parent_checkpoint_id, raw_metadata in row_cursor:
        rowids.append(int(rowid))
        last_checkpoint_id = checkpoint_id if isinstance(checkpoint_id, str) else None
        last_parent_checkpoint_id = parent_checkpoint_id if isinstance(parent_checkpoint_id, str) else None

        decoded = _decode_blob(raw_metadata)
        md = decoded if isinstance(decoded, dict) else {"_decoded": _safe_text(decoded)}
        last_metadata = md

        step_val = md.get("step")
        if isinstance(step_val, int):
            steps.append(step_val)

        source = md.get("source")
        if isinstance(source, str) and source:
            source_counts[source] += 1

    channel_counts = _collect_write_channel_counts(conn, thread_id)
    validation_hits, timeout_hits, rate_limit_hits = _scan_write_text_for_signals(conn, thread_id)

    step_min = min(steps) if steps else None
    step_max = max(steps) if steps else None
    step_unique_count = len(set(steps)) if steps else 0

    suspected_issue = "No clear pathological signal found"
    if validation_hits >= 3:
        suspected_issue = "Potential Pydantic ValidationError retry loop"
    elif rate_limit_hits > 0:
        suspected_issue = "OpenRouter rate-limit surfaced in write payloads"
    elif timeout_hits > 0:
        suspected_issue = "Timeout surfaced in write payloads"
    elif channel_counts.get("branch:to:executor_tools", 0) > 0 and channel_counts.get("messages", 0) > 0:
        suspected_issue = "Likely waiting/retrying around executor_tools branch"

    if step_max is not None and step_max >= 20 and "No clear" in suspected_issue:
        suspected_issue = "High step count indicates potential looping/replanning"

    return TaskCheckpointStats(
        task_id=task_id,
        thread_id=thread_id,
        checkpoint_count=len(rowids),
        step_min=step_min,
        step_max=step_max,
        step_unique_count=step_unique_count,
        source_counts=dict(source_counts),
        channel_counts=channel_counts,
        validation_error_hits=validation_hits,
        timeout_hits=timeout_hits,
        rate_limit_hits=rate_limit_hits,
        last_checkpoint_id=last_checkpoint_id,
        last_parent_checkpoint_id=last_parent_checkpoint_id,
        last_metadata=last_metadata,
        suspected_issue=suspected_issue,
        max_rowid=max(rowids) if rowids else -1,
    )


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    xs = list(range(1, len(values) + 1))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(values)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    numer = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
    return numer / denom


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    sorted_vals = sorted(values)
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


def _span_attr(span: Any, key: str) -> Any:
    if isinstance(span, dict):
        attrs = span.get("attributes")
        if isinstance(attrs, dict):
            return attrs.get(key)
        return None
    attrs = getattr(span, "attributes", None)
    if isinstance(attrs, dict):
        return attrs.get(key)
    return None


def _span_name(span: Any) -> str | None:
    if isinstance(span, dict):
        name = span.get("name")
        return name if isinstance(name, str) else None
    name = getattr(span, "name", None)
    return name if isinstance(name, str) else None


def _span_latency_ms(span: Any) -> float | None:
    # Best-effort parsing across phoenix-client versions.
    candidate_keys = ("latency_ms", "duration_ms", "latencyMs", "durationMs")
    if isinstance(span, dict):
        for key in candidate_keys:
            val = span.get(key)
            if isinstance(val, (int, float)):
                return float(val)

        st = span.get("start_time")
        et = span.get("end_time")
        if isinstance(st, datetime) and isinstance(et, datetime):
            return max(0.0, (et - st).total_seconds() * 1000.0)
        if isinstance(st, str) and isinstance(et, str):
            try:
                st_dt = datetime.fromisoformat(st.replace("Z", "+00:00"))
                et_dt = datetime.fromisoformat(et.replace("Z", "+00:00"))
                return max(0.0, (et_dt - st_dt).total_seconds() * 1000.0)
            except Exception:
                pass
        return None

    for key in candidate_keys:
        val = getattr(span, key, None)
        if isinstance(val, (int, float)):
            return float(val)

    st = getattr(span, "start_time", None)
    et = getattr(span, "end_time", None)
    if isinstance(st, datetime) and isinstance(et, datetime):
        return max(0.0, (et - st).total_seconds() * 1000.0)
    if isinstance(st, str) and isinstance(et, str):
        try:
            st_dt = datetime.fromisoformat(st.replace("Z", "+00:00"))
            et_dt = datetime.fromisoformat(et.replace("Z", "+00:00"))
            return max(0.0, (et_dt - st_dt).total_seconds() * 1000.0)
        except Exception:
            pass
    return None


def fetch_phoenix_latencies(
    *,
    phoenix_base_url: str,
    phoenix_project_name: str,
    task_ids_in_order: list[str],
    model_id: str,
    run_mode: str,
    lookback_hours: int,
) -> tuple[list[PhoenixLatency], str | None]:
    try:
        from phoenix.client import Client
    except Exception as exc:  # pragma: no cover
        return [], f"Phoenix client unavailable: {type(exc).__name__}: {exc}"

    client = Client(base_url=phoenix_base_url)

    candidates: list[str] = []
    if phoenix_project_name:
        candidates.append(phoenix_project_name)
    if "default" not in candidates:
        candidates.append("default")

    # Discover server-side project identifiers when available.
    try:
        projects_api = getattr(client, "projects", None)
        get_projects = getattr(projects_api, "get_projects", None)
        if callable(get_projects):
            discovered = get_projects(limit=200)
            for proj in discovered:
                if isinstance(proj, dict):
                    for key in ("identifier", "name", "id"):
                        val = proj.get(key)
                        if isinstance(val, str) and val and val not in candidates:
                            candidates.append(val)
                            break
                else:
                    for key in ("identifier", "name", "id"):
                        val = getattr(proj, key, None)
                        if isinstance(val, str) and val and val not in candidates:
                            candidates.append(val)
                            break
    except Exception:
        pass

    spans: list[Any] = []
    attempts: list[tuple[str, int]] = []
    for project_id in candidates:
        attempts.append((project_id, lookback_hours))
        attempts.append((project_id, max(lookback_hours, 24 * 7)))
    last_exc: Exception | None = None

    for project_id, hours in attempts:
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        kwargs: dict[str, Any] = {
            "project_identifier": project_id,
            "start_time": start_time,
            "limit": 10000,
            "timeout": 30,
        }

        try:
            spans = client.spans.get_spans(**kwargs)
        except Exception as exc:
            last_exc = exc
            continue

        if spans:
            break

    if not spans:
        if last_exc is not None:
            return [], f"Phoenix query failed: {type(last_exc).__name__}: {last_exc}"
        return [], "Phoenix query returned no spans for any fallback project/time window"

    wanted = set(task_ids_in_order)

    def collect_latencies(filter_level: str) -> dict[str, list[float]]:
        out: dict[str, list[float]] = defaultdict(list)
        for span in spans:
            span_name = _span_name(span)
            task_id = _span_attr(span, "scm.eval.task_id")
            model = _span_attr(span, "scm.eval.model_id")
            mode = _span_attr(span, "scm.eval.run_mode")

            if task_id not in wanted:
                continue

            if filter_level == "strict":
                if span_name != "scm.eval.task":
                    continue
                if model_id and model != model_id:
                    continue
                if run_mode and mode != run_mode:
                    continue
            elif filter_level == "name_and_task":
                if span_name != "scm.eval.task":
                    continue
            elif filter_level == "task_only":
                pass

            latency = _span_latency_ms(span)
            if isinstance(latency, (int, float)):
                out[str(task_id)].append(float(latency))
        return out

    latencies_by_task = collect_latencies("strict")
    if not any(latencies_by_task.values()):
        latencies_by_task = collect_latencies("name_and_task")
    if not any(latencies_by_task.values()):
        latencies_by_task = collect_latencies("task_only")

    rows: list[PhoenixLatency] = []
    for task_id in task_ids_in_order:
        vals = latencies_by_task.get(task_id, [])
        if not vals:
            continue
        rows.append(
            PhoenixLatency(
                task_id=task_id,
                count=len(vals),
                mean_ms=statistics.fmean(vals),
                p50_ms=_quantile(vals, 0.50),
                p95_ms=_quantile(vals, 0.95),
            )
        )

    return rows, None


def _format_ms(ms: float) -> str:
    return f"{ms:.1f}"


def build_report(
    *,
    checkpoint_rows: list[TaskCheckpointStats],
    phoenix_rows: list[PhoenixLatency],
    phoenix_error: str | None,
    final_task: TaskCheckpointStats | None,
    db_path: Path,
    phoenix_base_url: str,
    phoenix_project_name: str,
) -> str:
    lines: list[str] = []
    now_utc = datetime.now(timezone.utc).isoformat()

    lines.append("# Batch Stall Analysis (First 19 Attempted Tasks)")
    lines.append("")
    lines.append(f"Generated at: {now_utc}")
    lines.append(f"Checkpoint DB: `{db_path}`")
    lines.append(f"Phoenix URL: `{phoenix_base_url}`")
    lines.append(f"Phoenix project: `{phoenix_project_name}`")
    lines.append("")

    lines.append("## 1) Checkpoint Analysis (SQLite)")
    lines.append("")
    lines.append("### Task-by-task step/checkpoint distribution")
    lines.append("")
    lines.append("| Order | Task ID | Thread ID | Checkpoints | Step min | Step max | Unique steps | Signals |")
    lines.append("|---:|---|---|---:|---:|---:|---:|---|")
    for idx, row in enumerate(checkpoint_rows, start=1):
        signals = []
        if row.validation_error_hits:
            signals.append(f"validation={row.validation_error_hits}")
        if row.timeout_hits:
            signals.append(f"timeout={row.timeout_hits}")
        if row.rate_limit_hits:
            signals.append(f"rate_limit={row.rate_limit_hits}")
        signal_text = ", ".join(signals) if signals else "none"
        lines.append(
            f"| {idx} | {row.task_id} | {row.thread_id} | {row.checkpoint_count} | "
            f"{row.step_min if row.step_min is not None else '-'} | "
            f"{row.step_max if row.step_max is not None else '-'} | {row.step_unique_count} | {signal_text} |"
        )

    step_series = [float(r.step_max) for r in checkpoint_rows if r.step_max is not None]
    checkpoint_series = [float(r.checkpoint_count) for r in checkpoint_rows]
    step_slope = _linear_slope(step_series)
    chk_slope = _linear_slope(checkpoint_series)

    lines.append("")
    lines.append("### Distribution summary")
    lines.append("")
    if checkpoint_rows:
        lines.append(f"- Tasks analyzed: {len(checkpoint_rows)}")
        lines.append(f"- Mean checkpoints per task: {statistics.fmean(checkpoint_series):.2f}")
        lines.append(f"- P95 checkpoints per task: {_quantile(checkpoint_series, 0.95):.2f}")
        if step_series:
            lines.append(f"- Mean max-step per task: {statistics.fmean(step_series):.2f}")
            lines.append(f"- P95 max-step per task: {_quantile(step_series, 0.95):.2f}")
            lines.append(f"- Max-step trend slope (tasks 1->N): {step_slope:.3f} per task")
        lines.append(f"- Checkpoint-count trend slope (tasks 1->N): {chk_slope:.3f} per task")
    else:
        lines.append("- No checkpoint rows found.")

    lines.append("")
    lines.append("### Stall point diagnosis (latest attempted task)")
    lines.append("")
    if final_task is None:
        lines.append("- Unable to identify final task from checkpoint data.")
    else:
        lines.append(f"- Final task ID: `{final_task.task_id}`")
        lines.append(f"- Final thread ID: `{final_task.thread_id}`")
        lines.append(f"- Last checkpoint ID: `{final_task.last_checkpoint_id}`")
        lines.append(f"- Last parent checkpoint ID: `{final_task.last_parent_checkpoint_id}`")
        lines.append(f"- Source counts: `{json.dumps(final_task.source_counts, ensure_ascii=False)}`")
        lines.append(f"- Channel counts: `{json.dumps(final_task.channel_counts, ensure_ascii=False)}`")
        lines.append(f"- Detected issue: **{final_task.suspected_issue}**")
        if final_task.last_metadata:
            md_preview = json.dumps(final_task.last_metadata, ensure_ascii=False)
            if len(md_preview) > 1200:
                md_preview = md_preview[:1200] + "..."
            lines.append(f"- Last checkpoint metadata preview: `{md_preview}`")

    lines.append("")
    lines.append("## 2) Trace & Latency Analysis (Arize Phoenix)")
    lines.append("")
    if phoenix_error:
        lines.append(f"- Phoenix query error: {phoenix_error}")
    elif not phoenix_rows:
        lines.append("- No matching Phoenix latency spans found for the analyzed tasks.")
    else:
        lines.append("| Task ID | Span count | Mean latency ms | P50 ms | P95 ms |")
        lines.append("|---|---:|---:|---:|---:|")
        for row in phoenix_rows:
            lines.append(
                f"| {row.task_id} | {row.count} | {_format_ms(row.mean_ms)} | "
                f"{_format_ms(row.p50_ms)} | {_format_ms(row.p95_ms)} |"
            )

        ordered_means = [r.mean_ms for r in phoenix_rows]
        latency_slope = _linear_slope(ordered_means)
        lines.append("")
        lines.append(f"- Latency trend slope (task order): {latency_slope:.3f} ms/task")
        if latency_slope > 0:
            lines.append("- Interpretation: progressive slowdown signal present.")
        else:
            lines.append("- Interpretation: no progressive slowdown signal.")

    lines.append("")
    lines.append("## 3) Recommendations")
    lines.append("")
    lines.append("- Add a hard LangGraph step cap (for example 25-30) with explicit fail-fast error annotation.")
    lines.append("- Add per-node wall-clock timeouts around planner/executor/executor_tools transitions.")
    lines.append("- Add retry budget caps for repetitive validation failures; escalate after N retries.")
    lines.append("- Persist an explicit terminal status artifact per task (success, rate-limit, timeout, validation-loop).")
    lines.append("- Add a batch watchdog: if no new successful task completion within a time window, stop and emit diagnostics.")

    return "\n".join(lines) + "\n"


def run_analysis(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db)
    dataset_path = Path(args.dataset)
    report_path = Path(args.report)

    if not db_path.exists():
        raise FileNotFoundError(f"Checkpoint DB not found: {db_path}")
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    task_ids = _load_dataset_task_ids(dataset_path)

    with sqlite3.connect(str(db_path)) as conn:
        recent = _select_recent_task_threads(conn, dataset_task_ids=task_ids, task_limit=args.tasks)
        checkpoint_rows = [_analyze_task_thread(conn, task_id, thread_id) for task_id, thread_id, _ in recent]

    final_task = max(checkpoint_rows, key=lambda r: r.max_rowid) if checkpoint_rows else None

    task_ids_in_order = [r.task_id for r in checkpoint_rows]
    phoenix_rows, phoenix_error = fetch_phoenix_latencies(
        phoenix_base_url=args.phoenix_base_url,
        phoenix_project_name=args.phoenix_project,
        task_ids_in_order=task_ids_in_order,
        model_id=args.model_id,
        run_mode=args.run_mode,
        lookback_hours=args.phoenix_lookback_hours,
    )

    report_text = build_report(
        checkpoint_rows=checkpoint_rows,
        phoenix_rows=phoenix_rows,
        phoenix_error=phoenix_error,
        final_task=final_task,
        db_path=db_path,
        phoenix_base_url=args.phoenix_base_url,
        phoenix_project_name=args.phoenix_project,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    payload: dict[str, Any] = {
        "tasks_analyzed": [r.task_id for r in checkpoint_rows],
        "final_task": final_task.task_id if final_task else None,
        "final_thread_id": final_task.thread_id if final_task else None,
        "final_issue": final_task.suspected_issue if final_task else None,
        "phoenix_error": phoenix_error,
    }

    if args.json_out:
        json_out = Path(args.json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Post-mortem analyzer for stalled AgenticGraph batch runs.")
    parser.add_argument("--db", default="outputs/langgraph_checkpoints.sqlite", help="Path to LangGraph checkpoint SQLite DB.")
    parser.add_argument(
        "--dataset",
        default="data/benchmark/golden_tasks_questions_only.jsonl",
        help="Dataset used for task ordering and thread-id prefix parsing.",
    )
    parser.add_argument("--tasks", type=int, default=19, help="Number of most-recent attempted tasks to analyze.")
    parser.add_argument("--model-id", default="x-ai/grok-4.1-fast", help="Model ID filter for Phoenix latency spans.")
    parser.add_argument("--run-mode", default="AgenticGraph", help="Run mode filter for Phoenix latency spans.")
    parser.add_argument("--phoenix-base-url", default="http://127.0.0.1:6006", help="Phoenix base URL.")
    parser.add_argument("--phoenix-project", default="scm-cert-eval-sandbox", help="Phoenix project name.")
    parser.add_argument("--phoenix-lookback-hours", type=int, default=72, help="Lookback window for Phoenix span retrieval.")
    parser.add_argument(
        "--report",
        default="docs/reports/2026-04-16-batch-stall-analysis.md",
        help="Output Markdown report path.",
    )
    parser.add_argument(
        "--json-out",
        default="outputs/batch_stall_analysis_summary.json",
        help="Optional JSON summary output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run_analysis(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
