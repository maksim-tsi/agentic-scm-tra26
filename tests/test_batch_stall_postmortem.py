import json
import sqlite3
import sys
from pathlib import Path


def _init_db(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                type TEXT,
                checkpoint BLOB,
                metadata BLOB,
                PRIMARY KEY(thread_id, checkpoint_ns, checkpoint_id)
            );

            CREATE TABLE writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT,
                value BLOB,
                PRIMARY KEY(thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            );
            """
        )


def _insert_checkpoint(conn: sqlite3.Connection, *, thread_id: str, checkpoint_id: str, parent_id: str | None, step: int) -> None:
    metadata = json.dumps({"step": step, "source": "loop", "task_id": thread_id.split("_")[0]}).encode("utf-8")
    conn.execute(
        """
        INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata)
        VALUES (?, '', ?, ?, 'json', NULL, ?)
        """,
        (thread_id, checkpoint_id, parent_id, metadata),
    )


def _insert_write(conn: sqlite3.Connection, *, thread_id: str, checkpoint_id: str, idx: int, channel: str, text: str) -> None:
    conn.execute(
        """
        INSERT INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
        VALUES (?, '', ?, 'w', ?, ?, 'json', ?)
        """,
        (thread_id, checkpoint_id, idx, channel, text.encode("utf-8")),
    )


def test_select_recent_task_threads_and_validation_signal(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.adhoc import batch_stall_postmortem as m

    db_path = tmp_path / "checkpoints.sqlite"
    _init_db(db_path)

    with sqlite3.connect(str(db_path)) as conn:
        _insert_checkpoint(conn, thread_id="task_a_abcd1234", checkpoint_id="c1", parent_id=None, step=1)
        _insert_checkpoint(conn, thread_id="task_a_abcd1234", checkpoint_id="c2", parent_id="c1", step=2)

        _insert_checkpoint(conn, thread_id="task_b_eeee9999", checkpoint_id="c1", parent_id=None, step=1)
        _insert_checkpoint(conn, thread_id="task_b_eeee9999", checkpoint_id="c2", parent_id="c1", step=2)
        _insert_checkpoint(conn, thread_id="task_b_eeee9999", checkpoint_id="c3", parent_id="c2", step=3)

        _insert_write(
            conn,
            thread_id="task_b_eeee9999",
            checkpoint_id="c3",
            idx=0,
            channel="messages",
            text="pydantic ValidationError: missing required field",
        )
        _insert_write(
            conn,
            thread_id="task_b_eeee9999",
            checkpoint_id="c3",
            idx=1,
            channel="messages",
            text="ValidationError raised again",
        )
        _insert_write(
            conn,
            thread_id="task_b_eeee9999",
            checkpoint_id="c3",
            idx=2,
            channel="messages",
            text="pydantic validationerror loop suspected",
        )
        conn.commit()

    with sqlite3.connect(str(db_path)) as conn:
        selected = m._select_recent_task_threads(
            conn,
            dataset_task_ids=["task_a", "task_b", "task_c"],
            task_limit=2,
        )
        assert [task_id for task_id, _, _ in selected] == ["task_a", "task_b"]

        stats = [m._analyze_task_thread(conn, task_id, thread_id) for task_id, thread_id, _ in selected]

    task_b = next(s for s in stats if s.task_id == "task_b")
    assert task_b.step_max == 3
    assert task_b.validation_error_hits >= 3
    assert "ValidationError" in task_b.suspected_issue


def test_report_render_contains_final_task(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts.adhoc import batch_stall_postmortem as m

    row1 = m.TaskCheckpointStats(
        task_id="task_a",
        thread_id="task_a_x1",
        checkpoint_count=4,
        step_min=1,
        step_max=4,
        step_unique_count=4,
        source_counts={"loop": 4},
        channel_counts={"messages": 6},
        validation_error_hits=0,
        timeout_hits=0,
        rate_limit_hits=0,
        last_checkpoint_id="c4",
        last_parent_checkpoint_id="c3",
        last_metadata={"step": 4, "source": "loop"},
        suspected_issue="No clear pathological signal found",
        max_rowid=10,
    )
    row2 = m.TaskCheckpointStats(
        task_id="task_b",
        thread_id="task_b_x2",
        checkpoint_count=9,
        step_min=1,
        step_max=21,
        step_unique_count=21,
        source_counts={"loop": 9},
        channel_counts={"messages": 18, "branch:to:executor_tools": 9},
        validation_error_hits=0,
        timeout_hits=1,
        rate_limit_hits=0,
        last_checkpoint_id="c9",
        last_parent_checkpoint_id="c8",
        last_metadata={"step": 21, "source": "loop"},
        suspected_issue="Timeout surfaced in write payloads",
        max_rowid=22,
    )
    pr = [
        m.PhoenixLatency(task_id="task_a", count=1, mean_ms=100.0, p50_ms=100.0, p95_ms=100.0),
        m.PhoenixLatency(task_id="task_b", count=1, mean_ms=250.0, p50_ms=250.0, p95_ms=250.0),
    ]

    report = m.build_report(
        checkpoint_rows=[row1, row2],
        phoenix_rows=pr,
        phoenix_error=None,
        final_task=row2,
        db_path=tmp_path / "db.sqlite",
        phoenix_base_url="http://127.0.0.1:6006",
        phoenix_project_name="scm-cert-eval-sandbox",
    )

    assert "Final task ID: `task_b`" in report
    assert "Latency trend slope" in report
    assert "Recommendations" in report
