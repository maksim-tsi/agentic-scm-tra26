from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelProgress:
    model_id: str
    slug: str
    completed_unique_task_ids: int
    completed_agenticgraph_task_ids: int
    total_rows: int
    unique_model_ids: list[tuple[str, int]]
    notes: str


def _extract_python_string_list(path: Path, var_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        out: list[str] = []
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                out.append(elt.value)
                        return out
    raise ValueError(f"Unable to find list variable {var_name!r} in {path}")


def _extract_models_from_shell(path: Path, var_name: str) -> list[str]:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(var_name)}\s*=\s*\((.*?)\)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise ValueError(f"Unable to find shell array {var_name!r} in {path}")

    body = match.group(1)
    return re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body)


def _extract_openrouter_model(path: Path) -> str | None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("OPENROUTER_MODEL="):
            return line.split("=", 1)[1].strip() or None
    return None


def _load_benchmark_task_ids(path: Path) -> set[str]:
    task_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"Invalid task_id at {path}:{line_no}")
            task_ids.add(row["task_id"])
    return task_ids


def _slug(model_id: str) -> str:
    return model_id.replace("/", "-")


def _audit_model_progress(model_id: str, batches_dir: Path) -> ModelProgress:
    slug = _slug(model_id)
    jsonl_path = batches_dir / slug / "evaluation_results.jsonl"
    if not jsonl_path.exists():
        return ModelProgress(
            model_id=model_id,
            slug=slug,
            completed_unique_task_ids=0,
            completed_agenticgraph_task_ids=0,
            total_rows=0,
            unique_model_ids=[],
            notes="missing evaluation_results.jsonl",
        )

    completed_any: set[str] = set()
    completed_agentic: set[str] = set()
    model_counter: Counter[str] = Counter()
    total_rows = 0
    skipped_rows = 0

    with jsonl_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skipped_rows += 1
                continue

            if not isinstance(row, dict):
                skipped_rows += 1
                continue

            total_rows += 1
            task_id = row.get("task_id")
            run_mode = row.get("run_mode")
            row_model_id = row.get("model_id")

            if isinstance(row_model_id, str) and row_model_id:
                model_counter[row_model_id] += 1

            if isinstance(task_id, str) and task_id:
                completed_any.add(task_id)
                if run_mode == "AgenticGraph":
                    completed_agentic.add(task_id)

    notes = "ok"
    if skipped_rows:
        notes = f"ok (skipped_rows={skipped_rows})"

    return ModelProgress(
        model_id=model_id,
        slug=slug,
        completed_unique_task_ids=len(completed_any),
        completed_agenticgraph_task_ids=len(completed_agentic),
        total_rows=total_rows,
        unique_model_ids=model_counter.most_common(3),
        notes=notes,
    )


def _render_report(
    target_models: list[str],
    smoke_models: list[str],
    env_model: str | None,
    benchmark_total: int,
    progress_rows: list[ModelProgress],
) -> str:
    lines: list[str] = []
    lines.append("# Evaluation Matrix And Resume Logic Audit")
    lines.append("")
    lines.append("## 1. Target Models")
    lines.append("")
    lines.append("Official benchmark target models (from scripts/run_batch_phase1.sh):")
    for model in target_models:
        lines.append(f"- {model}")
    lines.append("")
    lines.append("Supporting model list (from scripts/smoke_test_infra.py DEFAULT_MODELS):")
    for model in smoke_models:
        lines.append(f"- {model}")
    lines.append("")
    lines.append(f"OPENROUTER_MODEL default in .env.example: {env_model or '<unset>'}")
    lines.append("")
    parity = "YES" if target_models == smoke_models else "NO"
    lines.append(f"Baseline parity (batch list == smoke list): {parity}")
    lines.append("")
    lines.append("## 2. Resume Safety")
    lines.append("")
    lines.append("Verdict: conditionally safe, not 100% safe across all invocation patterns.")
    lines.append("")
    lines.append("Evidence from scripts/batch_resume_runner.py:")
    lines.append("- Completed tasks are counted only when task_id is present and row_run_mode == run_mode and row_model_id == model_id.")
    lines.append("- With --model-id provided, results path is model-scoped: outputs/batches/<model-slug>/evaluation_results.jsonl.")
    lines.append("- Without --model-id (env-only model), legacy flat path is used: outputs/evaluation_results.jsonl.")
    lines.append("")
    lines.append("Conclusion:")
    lines.append("- Yes, skip checks are scoped by model_id filter.")
    lines.append("- No, storage scope is not always model-isolated unless --model-id is passed.")
    lines.append("- Operationally safe mode: always pass --model-id.")
    lines.append("")
    lines.append("## 3. Current Progress")
    lines.append("")
    lines.append(f"Benchmark total tasks: {benchmark_total}")
    lines.append("")
    lines.append("| Model | Folder Slug | Completed (unique task_id, any run_mode) | Completed (unique task_id, AgenticGraph) | Total Rows | Top model_id values in file | Notes |")
    lines.append("|---|---|---:|---:|---:|---|---|")
    for row in progress_rows:
        top_models = ", ".join(f"{mid} ({cnt})" for mid, cnt in row.unique_model_ids) or "-"
        lines.append(
            f"| {row.model_id} | {row.slug} | {row.completed_unique_task_ids}/{benchmark_total} | "
            f"{row.completed_agenticgraph_task_ids}/{benchmark_total} | {row.total_rows} | {top_models} | {row.notes} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit evaluation matrix and resume logic.")
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
        help="Optional output markdown path. Defaults to stdout.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    target_models = _extract_models_from_shell(repo_root / "scripts" / "run_batch_phase1.sh", "MODELS")
    smoke_models = _extract_python_string_list(repo_root / "scripts" / "smoke_test_infra.py", "DEFAULT_MODELS")
    env_model = _extract_openrouter_model(repo_root / ".env.example")
    benchmark_total = len(_load_benchmark_task_ids(repo_root / "data" / "benchmark" / "golden_tasks_questions_only.jsonl"))

    progress_rows = [
        _audit_model_progress(model_id, repo_root / "outputs" / "batches")
        for model_id in target_models
    ]

    report = _render_report(target_models, smoke_models, env_model, benchmark_total, progress_rows)
    if args.output is None:
        print(report)
    else:
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())