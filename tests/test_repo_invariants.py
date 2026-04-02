from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_agents_exists_and_is_short() -> None:
    agents = REPO_ROOT / "AGENTS.md"
    assert agents.exists()

    # Keep this as a small "map" per Harness Engineering guidance.
    lines = agents.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 140


def test_benchmark_schema_has_exact_keys() -> None:
    benchmark = REPO_ROOT / "data" / "benchmark" / "golden_tasks_questions_only.jsonl"
    assert benchmark.exists()

    expected = {"task_id", "scenario_context", "agent_prompt", "t_shirt_size"}
    for lineno, line in enumerate(benchmark.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        assert set(row.keys()) == expected, f"Line {lineno} has unexpected keys: {sorted(row.keys())}"


def test_tools_export_contract() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    import tools  # noqa: F401

    assert hasattr(tools, "ACTIVE_TOOLS")
    assert hasattr(tools, "__all__")

    exported = list(tools.__all__)
    assert "ACTIVE_TOOLS" in exported
    aliases = [name for name in exported if name != "ACTIVE_TOOLS"]
    assert len(aliases) == len(tools.ACTIVE_TOOLS)

    seen = set()
    for alias in aliases:
        assert "__" in alias
        obj = getattr(tools, alias)
        assert callable(obj)
        assert obj in tools.ACTIVE_TOOLS
        assert alias not in seen
        seen.add(alias)

    assert len(set(tools.ACTIVE_TOOLS)) == len(tools.ACTIVE_TOOLS)


def test_tools_registry_is_bootstrapped_from_manifest() -> None:
    manifest = REPO_ROOT / "tools" / "active_tools_manifest.json"
    assert manifest.exists()

    proc = subprocess.run(
        [sys.executable, "scripts/bootstrap_active_tools.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr

