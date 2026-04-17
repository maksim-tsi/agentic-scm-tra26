# Adhoc Analysis Scripts

This directory contains one-off or incident-response scripts that are useful for
operations and debugging but are not part of the benchmark runtime path.

Why this exists:
- Keeps emergency investigation code separate from core runner scripts.
- Makes post-mortem logic reproducible and reviewable.
- Encourages tests before execution for safer debugging under pressure.

Current scripts:
- `batch_stall_postmortem.py`: analyzes LangGraph SQLite checkpoints and Phoenix
  traces for a stalled AgenticGraph batch run, then writes a Markdown report.

Usage pattern:
1. Add or update tests under `tests/`.
2. Run targeted tests first.
3. Execute the script with explicit input/output paths.
