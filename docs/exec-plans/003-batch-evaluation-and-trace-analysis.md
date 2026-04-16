# Execution Plan 003 - Batch Evaluation and Trace Analysis

## Purpose
Define a controlled, resumable benchmark-evaluation workflow for TRA '26 paper experiments, starting with a 50-task sample in AgenticGraph mode. This plan emphasizes behavioral diagnostics before ground-truth scoring.

## Scope
In scope:
- Batch execution strategy (first 50 tasks, resumable runs).
- Behavioral diagnostics from checkpoints, JSONL outputs, and Phoenix/OTel traces.
- Go/No-Go quality gate before full-dataset execution.
- Full-dataset continuation strategy for remaining tasks.

Out of scope for this plan:
- Running the batch now.
- Modifying benchmark inputs in `data/benchmark/`.
- Redesigning model prompts or tool contracts.

## Preconditions
- Environment is reproducible (`uv` with lockfile) and repo setup is complete.
- Outputs directory is writable.
- OpenRouter and YAAM env vars are configured for AgenticGraph runs.
- Phoenix collector/project settings are configured if telemetry analysis is required.

## Phase 1 - Progress Tracking and Batch Execution Strategy

### 1.1 Progress tracking model (resumable by design)
Primary source of truth:
- `outputs/evaluation_results.jsonl` is the append-only run log.
- Each successful task attempt writes a row containing `task_id`, `run_mode`, `model_id`, and `execution_metrics`.

Tracking rule:
- Treat unique `task_id` values in JSONL as completed units for the current run-mode/model pair.
- For resumability, compute pending tasks as:
  - all benchmark task_ids
  - minus completed task_ids filtered by `run_mode=AgenticGraph` and target `model_id`.

Two operating modes:
1. Fresh batch run:
- If starting from empty/isolated output file, use `--limit 50` directly.

2. Resume-safe batch run:
- Use a lightweight wrapper script (proposed: `scripts/batch_select_tasks.py`) to:
  - parse benchmark order from `data/benchmark/golden_tasks_questions_only.jsonl`
  - parse completed IDs from `outputs/evaluation_results.jsonl`
  - emit the first N pending `task_id`s (N=50 for initial sample).
- Then invoke orchestrator once per emitted `task_id`.

Implementation note:
- To avoid mixing experiments across models, prefer model-scoped outputs, e.g.:
  - `outputs/batches/<model_slug>/evaluation_results.jsonl`
  - `outputs/batches/<model_slug>/evaluation_results_debug.jsonl`
  - `outputs/batches/<model_slug>/langgraph_checkpoints.sqlite` (optional, if/when checkpoint path becomes configurable)

### 1.2 Exact CLI command for first 50 tasks (starting fresh)
Run from repo root:

```bash
PYTHONPATH=src:. uv run python scripts/run_orchestrator.py \
  --run-mode AgenticGraph \
  --limit 50 \
  --output-jsonl outputs/evaluation_results.jsonl \
  --output-jsonl-debug outputs/evaluation_results_debug.jsonl
```

Recommended model pinning for reproducibility:

```bash
OPENROUTER_MODEL=<model_id> \
PYTHONPATH=src:. uv run python scripts/run_orchestrator.py \
  --run-mode AgenticGraph \
  --limit 50 \
  --output-jsonl outputs/evaluation_results.jsonl \
  --output-jsonl-debug outputs/evaluation_results_debug.jsonl
```

### 1.3 Resume strategy if batch is interrupted
Option A (manual):
- Parse completed IDs from JSONL.
- Run remaining IDs one-by-one with `--task-id <id>`.

Option B (scripted, preferred):
- `scripts/batch_resume_runner.py` reads JSONL and benchmark file, then iterates pending IDs until target sample size is reached.
- Script writes a run manifest:
  - model_id
  - run start/end timestamps
  - requested sample size
  - completed IDs
  - failed IDs (from debug JSONL)

## Phase 2 - Post-Batch Behavioral Analysis (Blind Evaluation)

Goal:
- Evaluate agent behavior quality before any accuracy/ground-truth comparisons.

Deliverable:
- A single analysis report per model for the 50-task sample, generated from deterministic scripts.

### 2.1 Diagnostics from LangGraph checkpoints (`outputs/langgraph_checkpoints.sqlite`)
Proposed script:
- `scripts/analysis/analyze_checkpoints_behavior.py`

Inputs:
- checkpoint SQLite path
- evaluation JSONL path
- optional model_id filter
- optional task_id allowlist

Outputs:
- `outputs/reports/<run_tag>/checkpoint_behavior_summary.json`
- `outputs/reports/<run_tag>/checkpoint_behavior_summary.md`

Metrics to compute:
1. Average graph steps per task:
- Define step count as number of checkpoint transitions or message-state updates per thread_id/task.
- Report mean, median, p90, max.

2. Pydantic ValidationError frequency:
- Detect tool-message content beginning with `Validation Error:`.
- Report:
  - count of tasks with >=1 validation error
  - avg validation errors per affected task
  - global validation-error rate per tool call

3. Tool utilization distribution:
- Extract tool call names from assistant tool_calls in checkpoint messages.
- Report:
  - frequency table by tool name
  - share of tasks where each tool appears
  - never-used tool list from `tools.ACTIVE_TOOLS`

4. L2 auto-store success rate:
- Primary detection path:
  - search for YAAM store-success signal in traces/log spans (if emitted).
- Fallback/heuristic path:
  - for each successful tool response, verify no YAAM write failure warning linked to that tool-call segment.
- Report:
  - estimated store-attempt count
  - estimated success count
  - failure count and failure taxonomy (env/config/network/timeout/other)

Important caveat:
- Because auto-store is runtime-managed and best-effort, direct success observability may require explicit span/log instrumentation fields. If absent, classify as `attempted_observable`, `attempted_unobservable`, `failed_observable`.

### 2.2 Diagnostics from execution results (`outputs/evaluation_results.jsonl`)
Proposed script:
- `scripts/analysis/analyze_execution_metrics_jsonl.py`

Metrics to extract:
- From `execution_metrics`:
  - `syntax_errors_caught` distribution
  - `successful_retry_attempt` distribution
  - `tools_called` counts per task
  - tool usage frequency from `tools_called`
- Additional operational metrics:
  - empty raw_response rate
  - duplicated task_id occurrences
  - per-task attempts count (if reruns occurred)

Outputs:
- `outputs/reports/<run_tag>/execution_metrics_summary.json`
- `outputs/reports/<run_tag>/execution_metrics_summary.md`

### 2.3 Diagnostics from Phoenix/OpenTelemetry (latency and token usage)
Proposed script:
- `scripts/analysis/analyze_phoenix_traces.py`

Collection strategy:
1. Identify spans for orchestrator task executions via attributes like:
- `scm.eval.task_id`
- `scm.eval.model_id`
- `scm.eval.run_mode`

2. Latency extraction:
- Use span start/end timestamps to compute:
  - per-task total latency
  - per-node latency breakdown where available (planner/executor/finalizer/tool)

3. Token/cost extraction (if available in span attributes):
- candidate fields:
  - `llm.token_count.prompt`
  - `llm.token_count.completion`
  - `llm.token_count.total`
  - provider/model-specific usage fields in OpenInference attributes
- If token fields are absent, report as `not_available` and provide latency-only analysis.

Outputs:
- `outputs/reports/<run_tag>/phoenix_latency_tokens.json`
- `outputs/reports/<run_tag>/phoenix_latency_tokens.md`

### 2.4 Consolidated blind-eval artifact
Proposed script:
- `scripts/analysis/build_blind_eval_dashboard.py`

Inputs:
- three summaries above

Output:
- `outputs/reports/<run_tag>/blind_eval_summary.md`
- `outputs/reports/<run_tag>/blind_eval_summary.json`

The summary should include:
- behavioral scorecard table
- top 5 failure modes
- top 5 tools by usage and bottom 5 by usage
- candidate remediation actions before full run

## Phase 3 - Go/No-Go Gate

Review meeting objective:
- Decide whether to execute remaining 69 tasks for this model.

### 3.1 Gate criteria (baseline thresholds)
1. Stability:
- No infinite-loop signatures detected.
- No crash storm (task-level hard failures <= 5% in 50-task sample).

2. Tool behavior quality:
- Quantitative tasks show non-trivial tool usage (expected SCM tool called in >= 90% of applicable tasks).
- ValidationError self-correction is present but bounded:
  - target: median ValidationError count per task <= 1
  - no pathological retries (p95 graph steps below agreed ceiling).

3. L2 persistence behavior:
- L2 auto-store triggered successfully on > 90% of successful deterministic tool calls where observability is available.
- If observability is partial, unresolved uncertainty must be explicitly accepted before proceeding.

4. Efficiency/cost envelope:
- Average total latency per task within budget target.
- Average token usage per task within budget target (or `N/A` with explicit sign-off if unavailable).

5. Output health:
- Empty `raw_response` rate <= 2%.
- No systemic regressions in `execution_metrics` fields.

### 3.2 Decision outcomes
- Go:
  - Proceed to Phase 4 using resumable continuation.

- Conditional Go:
  - Proceed with mitigations (e.g., model switch, timeout tuning, telemetry improvements).

- No-Go:
  - Pause full run, address top failure modes, rerun 50-task validation sample.

## Phase 4 - Full Dataset Execution (Remaining Tasks)

### 4.1 Remaining-task computation strategy
Given benchmark size 119:
- first batch: 50 tasks
- remaining: 69 tasks

Compute remaining set by JSONL diff:
- benchmark task_ids
- minus completed task_ids for (`run_mode=AgenticGraph`, target `model_id`)

### 4.2 Execution strategy
Preferred:
- Run remaining IDs explicitly via wrapper script to avoid duplicate work and preserve resumability.

CLI pattern per task:

```bash
PYTHONPATH=src:. uv run python scripts/run_orchestrator.py \
  --run-mode AgenticGraph \
  --task-id <pending_task_id> \
  --output-jsonl outputs/evaluation_results.jsonl \
  --output-jsonl-debug outputs/evaluation_results_debug.jsonl
```

Batch runner behavior:
- stop-on-error policy configurable (`continue` recommended with debug logging)
- checkpoint progress every task
- final manifest with completed/failed/pending IDs

### 4.3 Post-full-run closure
After all remaining tasks:
1. Re-run Phase 2 analysis scripts over full dataset.
2. Compare sample-vs-full distributions:
- step counts
- validation-error rates
- tool utilization
- latency/tokens
3. Freeze final artifacts in `outputs/reports/<run_tag>/` for paper analysis.

## Recommended Script Backlog (Implementation Order)
1. `scripts/analysis/analyze_execution_metrics_jsonl.py`
2. `scripts/analysis/analyze_checkpoints_behavior.py`
3. `scripts/analysis/analyze_phoenix_traces.py`
4. `scripts/analysis/build_blind_eval_dashboard.py`
5. Optional: `scripts/batch_resume_runner.py`

## Risks and Mitigations
Risk 1: Mixed experiments in a single JSONL file across models.
- Mitigation: use model-scoped output paths or strict filtering by `model_id`.

Risk 2: Limited L2 success observability.
- Mitigation: add explicit store attempt/success/failure span attributes in a follow-up instrumentation patch.

Risk 3: Checkpoint DB merges historical runs.
- Mitigation: filter by recent run window and task/model metadata from JSONL.

Risk 4: Phoenix token fields unavailable.
- Mitigation: treat as non-blocking for latency analysis; require explicit sign-off for budget uncertainty.

## Definition of Done
- 50-task AgenticGraph run is completed with resumable logs.
- Blind behavioral report is generated from checkpoints + JSONL + Phoenix.
- Go/No-Go decision is documented with threshold outcomes.
- Remaining 69-task execution plan is ready and resumable by JSONL-derived pending IDs.
