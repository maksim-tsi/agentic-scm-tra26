from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _load_task_order(dataset_path: Path) -> list[str]:
    ordered: list[str] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
                raise ValueError(f"Invalid task_id at {dataset_path}:{line_no}")
            ordered.append(row["task_id"])
    return ordered


def _parse_task_id_from_thread(thread_id: str, task_ids_desc: list[str]) -> str | None:
    for task_id in task_ids_desc:
        prefix = f"{task_id}_"
        if thread_id.startswith(prefix):
            return task_id
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect recent LangGraph checkpoints for attempted tasks.")
    parser.add_argument("--db", type=Path, default=Path("outputs/langgraph_checkpoints.sqlite"))
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/benchmark/golden_tasks_questions_only.jsonl"),
    )
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    ordered = _load_task_order(args.dataset)
    ordered_desc = sorted(ordered, key=len, reverse=True)
    task_to_index = {task_id: idx for idx, task_id in enumerate(ordered)}

    conn = sqlite3.connect(str(args.db))
    try:
        max_rowid = conn.execute("SELECT COALESCE(MAX(rowid), 0) FROM checkpoints").fetchone()[0]
        rows = conn.execute(
            "SELECT rowid, thread_id FROM checkpoints ORDER BY rowid DESC LIMIT ?",
            (args.limit,),
        ).fetchall()
    finally:
        conn.close()

    seen: set[str] = set()
    attempts: list[tuple[int, str, str | None, int | None]] = []
    for rowid_raw, thread_raw in rows:
        thread_id = str(thread_raw)
        task_id = _parse_task_id_from_thread(thread_id, ordered_desc)
        if task_id and task_id not in seen:
            seen.add(task_id)
            attempts.append((int(rowid_raw), thread_id, task_id, task_to_index.get(task_id)))

    print(f"checkpoint_max_rowid={int(max_rowid)}")
    print(f"recent_unique_tasks={len(attempts)}")
    for rowid, thread_id, task_id, index in attempts:
        idx_text = str(index) if isinstance(index, int) else "<unknown>"
        task_text = task_id or "<unparsed>"
        print(f"rowid={rowid} task_index={idx_text} task_id={task_text} thread_id={thread_id}")

    if attempts:
        max_idx = max(i for _, _, _, i in attempts if isinstance(i, int))
        print(f"max_task_index_seen={max_idx}")
        if max_idx + 1 < len(ordered):
            print(f"next_dataset_task_id_after_seen={ordered[max_idx + 1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())