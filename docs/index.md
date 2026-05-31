# Docs index

This directory is the public archive documentation for agent and evaluator behavior.
Internal development logs, dated experiment reports, and paper-drafting artifacts are intentionally kept out of the public archive tip.

## Read first
- `docs/public-archive.md` — archive scope and local-only exclusions.
- `docs/architecture.md` — repo map and boundaries (what is read-only / versioned).
- `docs/evaluation/contract.md` — evaluation I/O contracts and scoring expectations.

## How to run
- `scripts/run_orchestrator.py` — benchmark runner (RFC001 + RFC002), emits JSONL + Phoenix/OpenTelemetry traces.
  - Outputs:
    - `outputs/evaluation_results.jsonl` (RFC002 strict + row-aligned)
    - `outputs/evaluation_results_debug.jsonl` (exceptions only; rich postmortems)

## Prompts
- `docs/prompts/scm_agent_system_prompt.md` — benchmarked SCM agent “constitution” (soft format guidance).

## RFCs (design history)
- `docs/rfcs/000-ablation-benchmark-matrix.md` — placeholder for the upcoming evaluation ablation matrix.
- `docs/rfcs/001-native-tool-calling-evaluator.md` — tool calling evaluator design (strict Pydantic boundary; no code execution).
- `docs/rfcs/002-execution-metrics-telemetry.md` — RFC002 JSONL output schema + required Phoenix/OpenTelemetry attributes.
