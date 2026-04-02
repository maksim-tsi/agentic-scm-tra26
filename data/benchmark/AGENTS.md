# Benchmark Data — Agent Instructions

## Purpose
`data/benchmark/` contains the canonical, questions-only benchmark input set.

## Hard rules
- Treat `golden_tasks_questions_only.jsonl` as **immutable** for reproducibility.
- Do not add extra keys/fields to benchmark rows.
- Do not write generated artifacts into this directory.

## Schema (must hold for every row)
Exactly four keys per record:
- `task_id`
- `scenario_context`
- `agent_prompt`
- `t_shirt_size`

