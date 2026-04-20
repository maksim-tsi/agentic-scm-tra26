from __future__ import annotations

import argparse
import json
import pickle
import re
import sqlite3
import statistics
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None


TARGET_MODELS = [
    "x-ai/grok-4.1-fast",
    "meta-llama/llama-3.1-8b-instruct",
    "deepseek/deepseek-v3.2",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]


@dataclass(frozen=True)
class ModelStats:
    model_id: str
    slug: str
    unique_tasks: int
    total_rows: int
    ok_rows: int
    empty_rows: int
    debug_rows: int
    mismatch_rows: int
    total_tools_called: int
    unique_tools: int
    avg_tools_per_row: float
    dominant_language: str
    non_english_rows: int
    error_types: list[tuple[str, int]]


def _slug(model_id: str) -> str:
    return model_id.replace("/", "-")


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


def _load_benchmark_tasks(path: Path) -> list[str]:
    tasks: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"Invalid task_id at {path}:{line_no}")
            tasks.append(row["task_id"])
    return tasks


def _detect_language(text: str) -> str:
    if not text.strip():
        return "empty"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh_or_mixed"
    if re.search(r"[\u0400-\u04FF]", text):
        return "cyrillic_or_mixed"
    if re.search(r"[\u0600-\u06FF]", text):
        return "arabic_or_mixed"

    lowered = text.lower()
    english_markers = [" the ", " and ", " for ", " is ", " are ", " with ", " based on "]
    marker_hits = sum(1 for m in english_markers if m in f" {lowered} ")
    return "english" if marker_hits >= 2 else "undetermined_latin"


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _collect_model_stats(
    repo_root: Path,
    benchmark_total: int,
) -> tuple[list[ModelStats], Counter[str], Counter[str], dict[str, int], dict[str, int]]:
    batches_dir = repo_root / "outputs" / "batches"
    stats: list[ModelStats] = []
    global_error_types: Counter[str] = Counter()
    global_error_signatures: Counter[str] = Counter()
    language_global: Counter[str] = Counter()
    model_to_trace_ids: dict[str, int] = {}

    for model_id in TARGET_MODELS:
        slug = _slug(model_id)
        eval_path = batches_dir / slug / "evaluation_results.jsonl"
        debug_path = batches_dir / slug / "evaluation_results_debug.jsonl"

        eval_rows = _parse_jsonl(eval_path)
        debug_rows = _parse_jsonl(debug_path)

        unique_tasks = set()
        ok_rows = 0
        empty_rows = 0
        mismatch_rows = 0
        tool_counter: Counter[str] = Counter()
        language_counter: Counter[str] = Counter()
        error_types: Counter[str] = Counter()
        trace_ids = set()

        for row in eval_rows:
            task_id = row.get("task_id")
            if isinstance(task_id, str) and task_id:
                unique_tasks.add(task_id)

            row_model = row.get("model_id")
            if isinstance(row_model, str) and row_model and row_model != model_id:
                mismatch_rows += 1

            raw_response = row.get("raw_response")
            if isinstance(raw_response, str) and raw_response.strip():
                ok_rows += 1
            else:
                empty_rows += 1

            language = _detect_language(raw_response if isinstance(raw_response, str) else "")
            language_counter[language] += 1
            language_global[language] += 1

            execution_metrics = row.get("execution_metrics")
            if isinstance(execution_metrics, dict):
                tools_called = execution_metrics.get("tools_called")
                if isinstance(tools_called, list):
                    for tool in tools_called:
                        if isinstance(tool, str) and tool:
                            tool_counter[tool] += 1

        for row in debug_rows:
            err = row.get("error_type")
            if isinstance(err, str) and err:
                error_types[err] += 1
                global_error_types[err] += 1
            msg = row.get("error_message")
            msg_low = msg.lower() if isinstance(msg, str) else ""
            if "pydantic" in msg_low or "validation errors for" in msg_low:
                global_error_signatures["pydantic_validation"] += 1
            if "json invalid" in msg_low or "invalid json" in msg_low or "expected value at line" in msg_low:
                global_error_signatures["json_structure_or_parse"] += 1
            if "429" in msg_low or "rate limit" in msg_low:
                global_error_signatures["provider_rate_limit_429"] += 1
            if "502" in msg_low or "503" in msg_low or "504" in msg_low:
                global_error_signatures["provider_5xx_gateway"] += 1
            if "openrouter" in msg_low or "api" in msg_low or "provider" in msg_low:
                global_error_signatures["provider_or_api_related"] += 1
            trace_id = row.get("trace_id")
            if isinstance(trace_id, str) and len(trace_id) == 32:
                trace_ids.add(trace_id)

        model_to_trace_ids[model_id] = len(trace_ids)
        dominant_language = language_counter.most_common(1)[0][0] if language_counter else "none"
        non_english_rows = sum(
            count for lang, count in language_counter.items() if lang not in {"english", "empty"}
        )

        total_rows = len(eval_rows)
        total_tools = sum(tool_counter.values())
        avg_tools = total_tools / total_rows if total_rows else 0.0

        stats.append(
            ModelStats(
                model_id=model_id,
                slug=slug,
                unique_tasks=len(unique_tasks),
                total_rows=total_rows,
                ok_rows=ok_rows,
                empty_rows=empty_rows,
                debug_rows=len(debug_rows),
                mismatch_rows=mismatch_rows,
                total_tools_called=total_tools,
                unique_tools=len(tool_counter),
                avg_tools_per_row=avg_tools,
                dominant_language=dominant_language,
                non_english_rows=non_english_rows,
                error_types=error_types.most_common(8),
            )
        )

    baseline_map = _load_baseline_map(repo_root / "docs" / "reports" / "2026-04-20-medium-batch-initial-results.md")
    return stats, global_error_types, global_error_signatures, baseline_map, model_to_trace_ids


def _load_baseline_map(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    result: dict[str, int] = {}
    pattern = re.compile(r"\|\s*([^|]+?)\s*\|\s*(\d+)/(\d+)\s*\|")
    for match in pattern.finditer(content):
        model_id = match.group(1).strip()
        completed = int(match.group(2))
        if model_id in TARGET_MODELS:
            result[model_id] = completed
    return result


def _build_task_parser(task_ids: list[str]):
    ordered = sorted(task_ids, key=len, reverse=True)

    def _parse(thread_id: str) -> str | None:
        for task_id in ordered:
            if thread_id.startswith(f"{task_id}_"):
                return task_id
        return None

    return _parse


def _collect_checkpoint_metrics(repo_root: Path, task_ids: list[str]) -> dict[str, Any]:
    db_path = repo_root / "outputs" / "langgraph_checkpoints.sqlite"
    if not db_path.exists():
        return {
            "available": False,
            "attempts_per_task": {},
            "attempts_by_model": {},
            "thread_loop_depth": {},
            "yaam_retrieved_context_threads": 0,
            "max_rowid": 0,
            "notes": "checkpoint db missing",
        }

    parse_task = _build_task_parser(task_ids)

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT rowid, thread_id, metadata FROM checkpoints ORDER BY rowid ASC"
        ).fetchall()
        max_rowid = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM checkpoints").fetchone()[0]
        write_rows = conn.execute(
            "SELECT thread_id, channel, COUNT(*) FROM writes GROUP BY thread_id, channel"
        ).fetchall()
    finally:
        conn.close()

    thread_to_task: dict[str, str] = {}
    thread_to_model: dict[str, str] = {}
    thread_to_steps: dict[str, list[int]] = defaultdict(list)
    task_to_threads: dict[str, set[str]] = defaultdict(set)

    for _rowid, thread_raw, meta_raw in rows:
        thread_id = str(thread_raw)
        task_id = parse_task(thread_id)
        if task_id:
            thread_to_task[thread_id] = task_id
            task_to_threads[task_id].add(thread_id)

        decoded_meta = _decode_blob(meta_raw)
        if isinstance(decoded_meta, dict):
            model = decoded_meta.get("model_id")
            if isinstance(model, str) and model:
                thread_to_model[thread_id] = model
            step = decoded_meta.get("step")
            if isinstance(step, int):
                thread_to_steps[thread_id].append(step)

    attempts_per_task = {task_id: len(threads) for task_id, threads in task_to_threads.items()}
    attempts_by_model: Counter[str] = Counter()
    for thread_id, model_id in thread_to_model.items():
        if thread_id in thread_to_task:
            attempts_by_model[model_id] += 1

    thread_loop_depth: dict[str, int] = {}
    for thread_id, steps in thread_to_steps.items():
        if steps:
            thread_loop_depth[thread_id] = max(steps) - min(steps) + 1

    yaam_threads = set()
    for thread_raw, channel_raw, _count in write_rows:
        thread_id = str(thread_raw)
        channel = str(channel_raw)
        if channel == "retrieved_context":
            yaam_threads.add(thread_id)

    return {
        "available": True,
        "attempts_per_task": attempts_per_task,
        "attempts_by_model": dict(attempts_by_model),
        "thread_loop_depth": thread_loop_depth,
        "yaam_retrieved_context_threads": len(yaam_threads),
        "max_rowid": int(max_rowid),
        "notes": "ok",
    }


def _query_phoenix(repo_root: Path, trace_ids: set[str]) -> dict[str, Any]:
    if not trace_ids:
        return {
            "status": "no_trace_ids",
            "coverage": "0/0",
            "matched_spans": 0,
            "yaam_span_hits": 0,
            "tool_span_hits": 0,
            "errors": [],
        }

    env_path = repo_root / ".env"
    env_vars: dict[str, str] = {}
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_vars[key.strip()] = value.strip()

    base_url = env_vars.get("PHOENIX_BASE_URL")
    if not base_url:
        collector = env_vars.get("PHOENIX_COLLECTOR_ENDPOINT", "")
        if collector.endswith("/v1/traces"):
            base_url = collector[: -len("/v1/traces")]
        else:
            base_url = "http://127.0.0.1:6006"

    project = env_vars.get("PHOENIX_PROJECT_NAME") or "scm-cert-eval-sandbox"
    result: dict[str, Any] = {
        "status": "unknown",
        "base_url": base_url,
        "project": project,
        "coverage": f"0/{len(trace_ids)}",
        "matched_spans": 0,
        "yaam_span_hits": 0,
        "tool_span_hits": 0,
        "errors": [],
    }

    try:
        from phoenix.client import Client
    except Exception as exc:  # pragma: no cover
        result["status"] = "unavailable"
        result["errors"].append(f"phoenix client import failed: {type(exc).__name__}: {exc}")
        return result

    try:
        client = Client(base_url=base_url)
        spans = client.spans.get_spans(project_identifier=project, limit=2000)
        matched = 0
        matched_trace_ids: set[str] = set()
        yaam_hits = 0
        tool_hits = 0

        for span in spans:
            as_text = _safe_text(span)
            trace_match = re.search(r"'trace_id':\s*'([0-9a-fA-F]{32})'", as_text)
            trace_id = trace_match.group(1).lower() if trace_match else ""
            if trace_id and trace_id in trace_ids:
                matched += 1
                matched_trace_ids.add(trace_id)
                low = as_text.lower()
                if "/v2/memory/l" in low or "yaam" in low or "retrieved_context" in low:
                    yaam_hits += 1
                if "tool" in low or "executor_tools" in low:
                    tool_hits += 1

        result["status"] = "ok"
        result["matched_spans"] = matched
        result["yaam_span_hits"] = yaam_hits
        result["tool_span_hits"] = tool_hits
        result["coverage"] = f"{len(matched_trace_ids)}/{len(trace_ids)}"
        return result
    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(f"phoenix query failed: {type(exc).__name__}: {exc}")
        return result


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def _render_report(
    *,
    report_date: str,
    benchmark_total: int,
    model_stats: list[ModelStats],
    global_error_types: Counter[str],
    global_error_signatures: Counter[str],
    checkpoint: dict[str, Any],
    baseline_map: dict[str, int],
    phoenix: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# {report_date} Rerun Comprehensive Analysis")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    total_slots = sum(s.unique_tasks for s in model_stats)
    lines.append(
        f"This report analyzes rerun artifacts across 6 baseline models using JSONL outputs, LangGraph checkpoints, and Phoenix traces (best effort). "
        f"Aggregate completed task slots: {total_slots} over benchmark denominator {benchmark_total}."
    )
    lines.append("")

    lines.append("## 2. Data Sources and Method")
    lines.append("")
    lines.append("- Per-model outcomes: outputs/batches/*/evaluation_results.jsonl")
    lines.append("- Per-model errors: outputs/batches/*/evaluation_results_debug.jsonl")
    lines.append("- Attempt telemetry: outputs/langgraph_checkpoints.sqlite")
    lines.append("- Trace correlation: Phoenix spans via trace_id when available")
    lines.append("- Language detection: heuristic classifier (English markers + script detection)")
    lines.append("")

    lines.append("## 3. Run Coverage and Progress Matrix")
    lines.append("")
    lines.append("| Model | Unique Tasks | Rows | OK Rows | Empty Rows | Debug Rows | Delta vs 2026-04-20 Initial | model_id Mismatch |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in model_stats:
        delta = s.unique_tasks - baseline_map.get(s.model_id, 0)
        lines.append(
            f"| {s.model_id} | {s.unique_tasks}/{benchmark_total} | {s.total_rows} | {s.ok_rows} | {s.empty_rows} | "
            f"{s.debug_rows} | {delta:+d} | {s.mismatch_rows} |"
        )
    lines.append("")

    lines.append("## 4. Reliability and Error Taxonomy")
    lines.append("")
    if global_error_types:
        lines.append("Global error_type frequency:")
        for name, count in global_error_types.most_common(12):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("No debug error rows found.")
    lines.append("")
    lines.append("Per-model dominant errors:")
    for s in model_stats:
        if s.error_types:
            joined = ", ".join(f"{name} ({count})" for name, count in s.error_types[:3])
            lines.append(f"- {s.model_id}: {joined}")
        else:
            lines.append(f"- {s.model_id}: none observed")
    lines.append("")
    if global_error_signatures:
        lines.append("Error signature families (message-level):")
        for name, count in global_error_signatures.most_common():
            lines.append(f"- {name}: {count}")
        lines.append("")

    lines.append("## 5. Attempts, Retries, and Loop Dynamics (LangGraph)")
    lines.append("")
    if checkpoint.get("available"):
        attempts_per_task: dict[str, int] = checkpoint.get("attempts_per_task", {})
        loops: dict[str, int] = checkpoint.get("thread_loop_depth", {})
        attempt_values = list(attempts_per_task.values())
        loop_values = list(loops.values())
        lines.append(f"- Checkpoint max rowid: {checkpoint.get('max_rowid', 0)}")
        lines.append(f"- Tasks with at least one attempted thread: {len(attempts_per_task)}")
        lines.append(
            f"- Attempts per task (min/median/max): {min(attempt_values) if attempt_values else 0}/"
            f"{_median(attempt_values):.1f}/{max(attempt_values) if attempt_values else 0}"
        )
        lines.append(
            f"- Thread loop depth proxy (min/median/max): {min(loop_values) if loop_values else 0}/"
            f"{_median(loop_values):.1f}/{max(loop_values) if loop_values else 0}"
        )
        attempts_by_model = checkpoint.get("attempts_by_model", {})
        if attempts_by_model:
            lines.append("- Attempted threads by model_id from checkpoint metadata:")
            for model, count in sorted(attempts_by_model.items(), key=lambda kv: (-kv[1], kv[0])):
                lines.append(f"  - {model}: {count}")
        lines.append(
            f"- Threads with retrieved_context channel writes (YAAM L3 path evidence): {checkpoint.get('yaam_retrieved_context_threads', 0)}"
        )
    else:
        lines.append(f"Checkpoint analysis unavailable: {checkpoint.get('notes', 'unknown reason')}")
    lines.append("")

    lines.append("## 6. Tool and YAAM Utilization")
    lines.append("")
    lines.append("| Model | Total Tool Calls | Unique Tools | Avg Tools/Row |")
    lines.append("|---|---:|---:|---:|")
    for s in model_stats:
        lines.append(
            f"| {s.model_id} | {s.total_tools_called} | {s.unique_tools} | {s.avg_tools_per_row:.2f} |"
        )
    lines.append("")
    lines.append("YAAM evidence levels:")
    if checkpoint.get("available") and checkpoint.get("yaam_retrieved_context_threads", 0) > 0:
        lines.append("- Proven used: retrieved_context channel writes observed in LangGraph writes table.")
    else:
        lines.append("- Not proven from checkpoint writes; YAAM may still be called but not observable in current artifacts.")
    if phoenix.get("status") == "ok" and phoenix.get("yaam_span_hits", 0) > 0:
        lines.append("- Proven via traces: Phoenix spans include YAAM-related signatures.")
    elif phoenix.get("status") in {"error", "unavailable"}:
        lines.append("- Trace evidence unavailable due to Phoenix access/query limitations.")
    else:
        lines.append("- No YAAM-signature Phoenix spans matched current trace sample.")
    lines.append("")

    lines.append("## 7. Phoenix Trace Correlation")
    lines.append("")
    lines.append(f"- Phoenix status: {phoenix.get('status', 'unknown')}")
    lines.append(f"- Trace coverage (matched trace_ids / observed trace_ids): {phoenix.get('coverage', '0/0')}")
    lines.append(f"- Matched spans: {phoenix.get('matched_spans', 0)}")
    lines.append(f"- Tool-signature spans: {phoenix.get('tool_span_hits', 0)}")
    lines.append(f"- YAAM-signature spans: {phoenix.get('yaam_span_hits', 0)}")
    if phoenix.get("errors"):
        lines.append("- Phoenix query notes:")
        for err in phoenix["errors"]:
            lines.append(f"  - {err}")
    lines.append("")

    lines.append("## 8. Output Language Characteristics")
    lines.append("")
    lines.append("| Model | Dominant Language | Non-English Rows |")
    lines.append("|---|---|---:|")
    for s in model_stats:
        lines.append(f"| {s.model_id} | {s.dominant_language} | {s.non_english_rows} |")
    lines.append("")

    lines.append("## 9. Key Findings with Confidence")
    lines.append("")
    mismatch_total = sum(s.mismatch_rows for s in model_stats)
    lines.append(
        f"- Routing integrity: {'no model_id mismatches detected' if mismatch_total == 0 else f'{mismatch_total} mismatch rows detected'} (high confidence from JSONL)."
    )
    high_error_models = [s.model_id for s in model_stats if s.debug_rows > 0 and s.debug_rows >= s.ok_rows]
    if high_error_models:
        lines.append(f"- High-error lanes: {', '.join(high_error_models)} (high confidence from debug JSONL).")
    if checkpoint.get("available"):
        lines.append("- Loop/attempt dynamics measured from checkpoints (medium-high confidence; metadata decode dependent).")
    else:
        lines.append("- Loop/attempt dynamics unavailable due to missing checkpoint DB (low confidence for retry-depth claims).")
    if phoenix.get("status") == "ok":
        lines.append("- Trace linkage available but coverage depends on retained span window (medium confidence).")
    else:
        lines.append("- Trace linkage not available (low confidence for span-level latency claims).")
    lines.append("")

    lines.append("## 10. Threats to Validity and Gaps")
    lines.append("")
    lines.append("- Success proxy uses non-empty raw_response; this does not equal correctness against ground truth.")
    lines.append("- Language classification is heuristic and may undercount nuanced bilingual outputs.")
    lines.append("- YAAM L2/L4 success/failure is only partially observable from current artifacts.")
    lines.append("- Phoenix spans may be incomplete due to retention/query windows and endpoint availability.")
    lines.append("")

    lines.append("## 11. Recommendations")
    lines.append("")
    lines.append("1. Add structured YAAM operation result logging (success/failure + endpoint + latency) to JSONL artifacts.")
    lines.append("2. Add explicit attempt index and per-task retry counters to output rows for direct attempt analytics.")
    lines.append("3. Add normalized error signature extraction in pipeline to compare model reliability longitudinally.")
    lines.append("4. Add span attributes for node-level latency (planner/executor/finalizer) for publication-grade timing analysis.")
    lines.append("")

    lines.append("## 12. Reproducibility")
    lines.append("")
    lines.append("- Script: scripts/adhoc/comprehensive_rerun_analysis.py")
    lines.append("- Baseline comparison: docs/reports/2026-04-20-medium-batch-initial-results.md")
    lines.append("- Inputs: outputs/batches/*, outputs/langgraph_checkpoints.sqlite, data/benchmark/golden_tasks_questions_only.jsonl")
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate publication-grade rerun analysis report.")
    parser.add_argument("--date", required=True, help="Date label, e.g., 2026-04-20")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output markdown path. Defaults to docs/reports/<date>-rerun-comprehensive-analysis.md",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    benchmark_tasks = _load_benchmark_tasks(repo_root / "data" / "benchmark" / "golden_tasks_questions_only.jsonl")
    benchmark_total = len(set(benchmark_tasks))

    (
        model_stats,
        global_error_types,
        global_error_signatures,
        baseline_map,
        model_to_trace_ids,
    ) = _collect_model_stats(repo_root, benchmark_total)
    checkpoint = _collect_checkpoint_metrics(repo_root, benchmark_tasks)

    all_trace_ids: set[str] = set()
    for model_id in model_to_trace_ids:
        debug_rows = _parse_jsonl(repo_root / "outputs" / "batches" / _slug(model_id) / "evaluation_results_debug.jsonl")
        for row in debug_rows:
            trace_id = row.get("trace_id")
            if isinstance(trace_id, str) and len(trace_id) == 32:
                all_trace_ids.add(trace_id.lower())

    phoenix = _query_phoenix(repo_root, all_trace_ids)

    report_text = _render_report(
        report_date=args.date,
        benchmark_total=benchmark_total,
        model_stats=model_stats,
        global_error_types=global_error_types,
        global_error_signatures=global_error_signatures,
        checkpoint=checkpoint,
        baseline_map=baseline_map,
        phoenix=phoenix,
    )

    output_path = args.output
    if output_path is None:
        output_path = repo_root / "docs" / "reports" / f"{args.date}-rerun-comprehensive-analysis.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    print(f"Wrote report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())