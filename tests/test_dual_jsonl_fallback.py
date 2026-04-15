import json
import sys
import types
from pathlib import Path


def test_dual_jsonl_row_alignment_on_exception(monkeypatch, tmp_path: Path) -> None:
    # Ensure repo root is importable so `import scripts.run_orchestrator` works (namespace package).
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import scripts.run_orchestrator as run_orchestrator

    # Avoid importing the full tool registry (not needed for this test).
    dummy_tools = types.ModuleType("tools")
    dummy_tools.ACTIVE_TOOLS = []
    monkeypatch.setitem(sys.modules, "tools", dummy_tools)

    monkeypatch.setattr(run_orchestrator, "build_tool_registry", lambda _tools: ([], {}, {}))
    monkeypatch.setattr(run_orchestrator, "_openrouter_client", lambda _config: object())
    monkeypatch.setattr(run_orchestrator.time, "sleep", lambda _secs: None)

    tasks = {
        "task_fail": run_orchestrator.TaskRow(
            task_id="task_fail",
            scenario_context="ctx",
            agent_prompt="prompt",
            t_shirt_size="S",
        ),
        "task_ok": run_orchestrator.TaskRow(
            task_id="task_ok",
            scenario_context="ctx",
            agent_prompt="prompt",
            t_shirt_size="S",
        ),
    }
    monkeypatch.setattr(run_orchestrator, "load_tasks", lambda _path: tasks)

    call_order: list[str] = []

    class _DummyMetrics:
        def to_json(self) -> dict[str, object]:
            return {"syntax_errors_caught": 0, "successful_retry_attempt": 0, "tools_called": []}

    def _run_task_stub(*, task, **_kwargs):
        call_order.append(task.task_id)
        if task.task_id == "task_fail":
            raise RuntimeError("boom")
        return "ok", _DummyMetrics()

    monkeypatch.setattr(run_orchestrator, "run_task", _run_task_stub)

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    main_path = tmp_path / "evaluation_results.jsonl"
    debug_path = tmp_path / "evaluation_results_debug.jsonl"

    rc = run_orchestrator.main(
        [
            "--model-id",
            "test-model",
            "--run-mode",
            "Tools",
            "--output-jsonl",
            str(main_path),
            "--output-jsonl-debug",
            str(debug_path),
            "--no-tracing",
        ]
    )

    assert call_order == ["task_fail", "task_ok"]
    assert rc == 1

    main_rows = [json.loads(line) for line in main_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    debug_rows = [json.loads(line) for line in debug_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(main_rows) == 2
    assert len(debug_rows) == 1

    for row in main_rows:
        assert set(row.keys()) == {"task_id", "model_id", "run_mode", "raw_response", "execution_metrics"}
        assert set(row["execution_metrics"].keys()) == {"syntax_errors_caught", "successful_retry_attempt", "tools_called"}

    fail_row = main_rows[0]
    ok_row = main_rows[1]

    assert fail_row["task_id"] == "task_fail"
    assert fail_row["raw_response"] == ""
    assert fail_row["execution_metrics"] == {"syntax_errors_caught": 0, "successful_retry_attempt": 0, "tools_called": []}

    assert ok_row["task_id"] == "task_ok"
    assert ok_row["raw_response"] == "ok"

    dbg = debug_rows[0]
    assert dbg["task_id"] == "task_fail"
    assert dbg["error_message"] == "boom"
    assert "traceback" in dbg

