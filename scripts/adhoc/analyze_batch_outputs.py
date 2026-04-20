from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


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
    total_rows: int
    unique_tasks: int
    ok_rows: int
    err_rows: int
    debug_rows: int
    model_mismatch_rows: int
    top_model_ids: list[tuple[str, int]]
    notes: str


def _slug(model_id: str) -> str:
    return model_id.replace("/", "-")


def _load_benchmark_total(path: Path) -> int:
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"Invalid benchmark row at {path}:{line_no}")
            seen.add(row["task_id"])
    return len(seen)


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            if raw.strip():
                count += 1
    return count


def _analyze_model(model_id: str, batches_dir: Path) -> ModelStats:
    slug = _slug(model_id)
    model_dir = batches_dir / slug
    eval_path = model_dir / "evaluation_results.jsonl"
    debug_path = model_dir / "evaluation_results_debug.jsonl"

    if not eval_path.exists():
        return ModelStats(
            model_id=model_id,
            slug=slug,
            total_rows=0,
            unique_tasks=0,
            ok_rows=0,
            err_rows=0,
            debug_rows=_count_jsonl_rows(debug_path),
            model_mismatch_rows=0,
            top_model_ids=[],
            notes="missing evaluation_results.jsonl",
        )

    total_rows = 0
    ok_rows = 0
    err_rows = 0
    mismatches = 0
    unique_tasks: set[str] = set()
    model_ids: Counter[str] = Counter()
    skipped = 0

    with eval_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            if not isinstance(row, dict):
                skipped += 1
                continue

            total_rows += 1

            task_id = row.get("task_id")
            if isinstance(task_id, str) and task_id:
                unique_tasks.add(task_id)

            row_model_id = row.get("model_id")
            if isinstance(row_model_id, str) and row_model_id:
                model_ids[row_model_id] += 1
                if row_model_id != model_id:
                    mismatches += 1

            raw_response = row.get("raw_response")
            if isinstance(raw_response, str) and raw_response.strip():
                ok_rows += 1
            else:
                err_rows += 1

    notes = "ok"
    if skipped:
        notes = f"ok (skipped_rows={skipped})"

    return ModelStats(
        model_id=model_id,
        slug=slug,
        total_rows=total_rows,
        unique_tasks=len(unique_tasks),
        ok_rows=ok_rows,
        err_rows=err_rows,
        debug_rows=_count_jsonl_rows(debug_path),
        model_mismatch_rows=mismatches,
        top_model_ids=model_ids.most_common(3),
        notes=notes,
    )


def _render_report(stats: list[ModelStats], benchmark_total: int, report_date: str) -> str:
    lines: list[str] = []
    lines.append(f"# {report_date} Medium Batch Initial Results")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("Analysis of current artifacts under outputs/batches for the 6 baseline models after runtime model override fix.")
    lines.append("")
    lines.append(f"Benchmark denominator: {benchmark_total} tasks")
    lines.append("")
    lines.append("## Per-Model Summary")
    lines.append("")
    lines.append("| Model | Progress (unique tasks) | Rows | OK Rows | ERR Rows | Debug Rows | model_id Mismatch Rows | Top model_id values | Notes |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---|")
    for row in stats:
        top_ids = ", ".join(f"{mid} ({cnt})" for mid, cnt in row.top_model_ids) or "-"
        lines.append(
            f"| {row.model_id} | {row.unique_tasks}/{benchmark_total} | {row.total_rows} | {row.ok_rows} | {row.err_rows} | "
            f"{row.debug_rows} | {row.model_mismatch_rows} | {top_ids} | {row.notes} |"
        )

    lines.append("")
    lines.append("## Key Findings")
    lines.append("")

    mismatch_models = [s for s in stats if s.model_mismatch_rows > 0]
    if mismatch_models:
        lines.append("- Model routing inconsistency still present in these folders:")
        for s in mismatch_models:
            lines.append(f"  - {s.slug}: {s.model_mismatch_rows} mismatched rows")
    else:
        lines.append("- No model_id mismatches detected in current evaluation_results.jsonl rows.")

    stalled_models = [s for s in stats if s.unique_tasks == 0]
    if stalled_models:
        lines.append("- Models with no completed tasks yet:")
        for s in stalled_models:
            lines.append(f"  - {s.model_id}")

    total_unique = sum(s.unique_tasks for s in stats)
    lines.append(f"- Aggregate completed task slots across model runs: {total_unique} (sum across model folders).")
    lines.append("")
    lines.append("## Recommended Next Steps")
    lines.append("")
    lines.append("1. Continue 20-task batches for models with lowest progress until all models reach comparable coverage.")
    lines.append("2. Watch debug JSONL growth; if ERR rows rise, triage by error_type from evaluation_results_debug.jsonl.")
    lines.append("3. Re-run this report after each batch wave to track parity and model routing integrity.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze model batch outputs and generate markdown report.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root path.",
    )
    parser.add_argument("--date", required=True, help="Report date in YYYY-MM-DD format.")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output markdown path.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    benchmark_total = _load_benchmark_total(repo_root / "data" / "benchmark" / "golden_tasks_questions_only.jsonl")
    batches_dir = repo_root / "outputs" / "batches"

    stats = [_analyze_model(model_id, batches_dir) for model_id in TARGET_MODELS]
    report_text = _render_report(stats, benchmark_total, args.date)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report_text + "\n", encoding="utf-8")
    print(f"Wrote report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())