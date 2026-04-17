from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


TASK_TIMEOUT_SECONDS = 300


def _load_all_task_ids(dataset_path: Path) -> list[str]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    task_ids: list[str] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {dataset_path} at line {line_no}: {exc}") from exc

            task_id = row.get("task_id") if isinstance(row, dict) else None
            if not isinstance(task_id, str) or not task_id:
                raise ValueError(f"Missing/invalid task_id in {dataset_path} at line {line_no}")
            task_ids.append(task_id)

    return task_ids


def _load_completed_task_ids(results_path: Path, *, run_mode: str, model_id: str) -> set[str]:
    completed: set[str] = set()
    if not results_path.exists():
        return completed

    with results_path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Keep resume runner robust against partial/corrupt trailing lines.
                continue

            if not isinstance(row, dict):
                continue

            row_task_id = row.get("task_id")
            row_run_mode = row.get("run_mode")
            row_model_id = row.get("model_id")

            if (
                isinstance(row_task_id, str)
                and row_task_id
                and row_run_mode == run_mode
                and row_model_id == model_id
            ):
                completed.add(row_task_id)

    return completed


def _model_slug(model_id: str) -> str:
    return model_id.replace("/", "-")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Resumable batch runner for orchestrator tasks.")
    parser.add_argument("--limit", type=int, default=50, help="Number of pending tasks to process.")
    parser.add_argument("--run-mode", default="AgenticGraph", help="Run mode for orchestrator invocation.")
    parser.add_argument(
        "--model-id",
        default=None,
        help="Model identifier. Falls back to OPENROUTER_MODEL env var.",
    )
    args = parser.parse_args(argv)

    model_id = args.model_id or os.getenv("OPENROUTER_MODEL")
    if not model_id:
        print("ERROR: model id not provided and OPENROUTER_MODEL is not set.", file=sys.stderr)
        return 2

    if args.limit <= 0:
        print("ERROR: --limit must be a positive integer.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    dataset_path = repo_root / "data" / "benchmark" / "golden_tasks_questions_only.jsonl"

    # Preserve legacy default path when model is sourced from env only.
    if args.model_id:
        slug = _model_slug(model_id)
        batch_dir = repo_root / "outputs" / "batches" / slug
        batch_dir.mkdir(parents=True, exist_ok=True)
        results_path = batch_dir / "evaluation_results.jsonl"
        debug_path = batch_dir / "evaluation_results_debug.jsonl"
    else:
        results_path = repo_root / "outputs" / "evaluation_results.jsonl"
        debug_path = repo_root / "outputs" / "evaluation_results_debug.jsonl"

    all_task_ids = _load_all_task_ids(dataset_path)
    completed = _load_completed_task_ids(results_path, run_mode=args.run_mode, model_id=model_id)

    pending = [task_id for task_id in all_task_ids if task_id not in completed]
    batch = pending[: args.limit]

    print(f"Model: {model_id}")
    print(f"Run mode: {args.run_mode}")
    print(f"Output JSONL: {results_path}")
    print(f"Output debug JSONL: {debug_path}")
    print(f"Dataset tasks: {len(all_task_ids)}")
    print(f"Completed matching tasks: {len(completed)}")
    print(f"Pending matching tasks: {len(pending)}")
    print(f"Batch size requested: {args.limit}")
    print(f"Batch size selected: {len(batch)}")

    if not batch:
        print("No pending tasks to run for this model/run_mode filter.")
        return 0

    env = os.environ.copy()

    for i, task_id in enumerate(batch, start=1):
        print()
        print(f"=== Running task {i}/{len(batch)}: {task_id} ===")
        cmd = [
            sys.executable,
            "scripts/run_orchestrator.py",
            "--run-mode",
            args.run_mode,
            "--task-id",
            task_id,
            "--output-jsonl",
            str(results_path),
            "--output-jsonl-debug",
            str(debug_path),
        ]
        try:
            proc = subprocess.run(cmd, env=env, timeout=TASK_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            print(
                f"[TIMEOUT] task {task_id} exceeded {TASK_TIMEOUT_SECONDS}s wall-clock limit; continuing.",
                file=sys.stderr,
            )
            continue

        if proc.returncode != 0:
            print(
                f"WARNING: task {task_id} exited with code {proc.returncode}; continuing.",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
