# Development Log

This file tracks implementation activities in this repository and serves as a handoff log for future developers.

Standards alignment:
- Documentation system-of-record lives under docs.
- Runtime artifacts stay out of docs and outputs are written only to outputs where applicable.
- Benchmark and tool boundaries are preserved.

## Current Status Snapshot

Last updated: 2026-04-15
Project phase: Telemetry + resilience hardening (pre-LangGraph)
Overall status: Native orchestrator ready for benchmark runs (row-aligned JSONL + optional tracing)

## Progress Tracker

| ID | Task | Status | Date | Owner | Notes |
|---|---|---|---|---|---|
| DEV-001 | Review smoke docs and env requirements | Completed | 2026-04-02 | Copilot | Confirmed required vars and run order from docs and scripts |
| DEV-002 | Execute connectivity canary | Completed | 2026-04-02 | Copilot | Canary passed after parser fix |
| DEV-003 | Add explicit Phoenix endpoint fetch validation | Completed | 2026-04-02 | Copilot | Independent API retrieval confirmed parent-child trace linkage |
| DEV-004 | Fix Phoenix span parsing robustness | Completed | 2026-04-02 | Copilot | Added dict-safe handling in smoke_test_infra.py |
| DEV-005 | Harden model output reliability | Completed | 2026-04-02 | Copilot | Increased and parameterized token budget via SMOKE_TEST_MAX_TOKENS |
| DEV-006 | Execute full default smoke suite | Completed | 2026-04-02 | Copilot | All default models passed in final run |
| DEV-007 | Publish dated implementation report | Completed | 2026-04-02 | Copilot | Report created in docs/reports |
| DEV-008 | Implement native tool-calling orchestrator | Completed | 2026-04-02 | Codex | RFC001 loop + RFC002 JSONL + OTel span attributes |
| DEV-009 | Add orchestrator CLI runner script | Completed | 2026-04-02 | Codex | `scripts/run_orchestrator.py` loads tasks, emits traces + JSONL |
| DEV-010 | Telemetry + resilience hardening | Completed | 2026-04-15 | Codex | trace propagation, 1 task = 1 session, dual JSONL debug fallback, `--no-tracing` |

## Activity Log

### 2026-04-02

Summary:
- Performed implementation and execution of infra smoke validation.
- Added required explicit Phoenix API verification as a hard gate for operational health.
- Resolved two reliability issues in smoke validation logic.

Additional work:
- Implemented the first-pass orchestrator that follows RFC 001 (native tool calling, strict Pydantic boundary, 5-try ValidationError loop) and RFC 002 (evaluation JSONL output + required `scm.eval.*` span attributes).

Changes made:
1. scripts/smoke_test_infra.py
- Added support for dict-based span records returned by Phoenix client.
- Updated parent span name extraction to support dict and object payloads.
- Added configurable completion budget using SMOKE_TEST_MAX_TOKENS with a safer default.

2. src/orchestrator_native_tool_calling.py
- Loads benchmark tasks from `data/benchmark/golden_tasks_questions_only.jsonl` with strict key enforcement.
- Builds OpenAI tool schemas from `tools.ACTIVE_TOOLS` (Pydantic `Input.model_json_schema()`).
- Executes RFC001 tool loop in-process (no subprocess), including:
  - max 5 ValidationError retries
  - tool execution via allowlisted Python callables
  - tool-cycle cap to prevent infinite loops

3. scripts/run_orchestrator.py
- CLI runner for the orchestrator.
- Initializes Phoenix tracing via `phoenix.otel.register(..., auto_instrument=True)` and attaches required `scm.eval.*` attributes on the parent evaluation span.
- Appends RFC002 JSONL rows to `outputs/evaluation_results.jsonl` after each task.

How to run (example):
- `uv run python scripts/run_orchestrator.py --model-id x-ai/grok-4.1-fast --run-mode Tools --task-id newsvendor_covid_port_analysis`

Validation completed:
- Dependency sync completed with uv lock.
- Canary model run passed.
- Full default model run passed.
- Independent Phoenix API trace fetch confirmed expected span attributes and output text across all default models.

Related report:
- docs/reports/2026-04-02-infra-smoke-test-results.md

### 2026-04-15

Summary:
- Implemented strict “1 Task = 1 Session” mapping for Phoenix via `session.id = "task-<task_id>"`.
- Added best-effort W3C trace propagation into OpenRouter calls via `extra_headers` (`traceparent` + `x-trace-id`).
- Hardened benchmark runner resilience:
  - Tracing init failure no longer aborts the benchmark (warns and continues).
  - Added `--no-tracing` flag.
  - Added dual JSONL outputs with row alignment guarantees:
    - `outputs/evaluation_results.jsonl` remains RFC002 strict and always emits 1 row per task (fallback row on exception).
    - `outputs/evaluation_results_debug.jsonl` captures exceptions with traceback and partial response salvage.

Validation completed:
- Added and ran a pytest that intentionally raises inside `run_task` and confirms:
  - main JSONL stays row-aligned (fallback row written)
  - debug JSONL receives the rich postmortem row
  - main loop continues to subsequent tasks

## Open Follow-Ups

1. Consider promoting independent Phoenix verification snippet into a dedicated script for CI reuse.
2. Consider adding CLI option for max tokens in smoke script for clearer run-time tuning.
3. Optionally evaluate BatchSpanProcessor mode for production-like tracing throughput tests.

## Developer Handoff Notes

- If smoke fails with code 2, check env and dependency setup first.
- If smoke fails with code 1, inspect model output mismatch versus Phoenix trace timeout separately.
- Preserve reproducibility boundaries:
  - Do not modify benchmark inputs in data/benchmark.
  - Avoid silent behavior changes in tools unless versioned intentionally.
