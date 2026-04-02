# RFC 002 — Execution Metrics & Telemetry Schema

## Status
Draft (2026-04-02)

## Goal
Define a standard, machine-readable output schema for evaluation runs and a framework-agnostic OpenTelemetry attribute mapping for Arize Phoenix.

This RFC standardizes two artifacts:

1) The per-task JSON object appended to `outputs/evaluation_results.jsonl` (one line per evaluated task).
2) The required OpenTelemetry attributes that MUST be attached to the evaluation trace so Phoenix can filter and aggregate runs (project: `PHOENIX_PROJECT_NAME=scm-cert-eval-sandbox`).

## JSONL Output Schema (`outputs/evaluation_results.jsonl`)
After evaluating each task, the orchestrator MUST append exactly one JSON object (one line) to:

- `outputs/evaluation_results.jsonl`

### Top-level object (required keys)
Each JSONL row MUST be a JSON object with exactly these top-level keys:

- `task_id` (string)
- `model_id` (string; example: `"grok-4.1-fast"`)
- `run_mode` (string enum: `"Naive" | "Naive+Evidence" | "Tools" | "Tools+Evidence"`)
- `raw_response` (string; the final assistant answer content; use `""` if no final answer is produced)
- `execution_metrics` (object; required keys below)

### `execution_metrics` object (required keys)
`execution_metrics` MUST be a JSON object with exactly these keys:

- `syntax_errors_caught` (int)
  - Definition: number of Pydantic `ValidationError` exceptions caught by the orchestrator and fed back to the LLM for self-correction.
  - Expected range in v0: `0..5` (aligned to the max validation retry loop), but stored as a plain integer.
- `successful_retry_attempt` (int)
  - Definition: which validation retry attempt (1–5) produced the first schema-valid tool call payload.
  - Values:
    - `1..5`: the retry attempt index that succeeded.
    - `0`: v0 convention meaning either:
      - the run failed after max retries (no schema-valid payload), OR
      - the tool loop was never entered (e.g., Naive modes or tool-enabled modes where the model never called tools).
  - Analysis note: disambiguate using `tools_called` and/or additional failure metadata stored elsewhere (e.g., trace events).
- `tools_called` (list of strings)
  - Definition: allowlisted tool aliases actually executed by the orchestrator, in chronological order.
  - Example item: `"economic_order_quantity__calculate_total_annual_inventory_cost"`.
  - Empty list if no tools were executed.

### Mode semantics (v0)
The orchestrator MUST populate these fields consistently across modes:

- For `run_mode` in `"Naive"` or `"Naive+Evidence"`:
  - `execution_metrics.syntax_errors_caught = 0`
  - `execution_metrics.successful_retry_attempt = 0`
  - `execution_metrics.tools_called = []`

- For tool-enabled modes (`"Tools"`, `"Tools+Evidence"`) where the model never calls tools:
  - `execution_metrics.syntax_errors_caught = 0`
  - `execution_metrics.successful_retry_attempt = 0`
  - `execution_metrics.tools_called = []`

### Canonical examples
Successful tool-enabled run (one JSONL line):

```json
{"task_id":"task_00123","model_id":"grok-4.1-fast","run_mode":"Tools","raw_response":"<FINAL_ANSWER>...</FINAL_ANSWER>","execution_metrics":{"syntax_errors_caught":2,"successful_retry_attempt":3,"tools_called":["economic_order_quantity__calculate_total_annual_inventory_cost"]}}
```

Failed run after max validation retries (one JSONL line):

```json
{"task_id":"task_00456","model_id":"grok-4.1-fast","run_mode":"Tools+Evidence","raw_response":"","execution_metrics":{"syntax_errors_caught":5,"successful_retry_attempt":0,"tools_called":[]}}
```

## Arize Phoenix / OpenTelemetry mapping (framework-agnostic)
To support trace-driven refinement and filtering in Phoenix, the following attributes MUST be attached to the evaluation trace (ideally the span that represents “evaluate one task”, or the framework-equivalent primary span):

- `scm.eval.task_id` (string; same as `task_id`)
- `scm.eval.model_id` (string; same as `model_id`)
- `scm.eval.run_mode` (string; same as `run_mode`)
- `scm.eval.syntax_errors_caught` (int; same as `execution_metrics.syntax_errors_caught`)

### Implementation guideline (do not hardcode one approach)
The mechanism used to attach these attributes MUST follow the orchestration framework’s best practices:

- **Pure Python / standard OpenAI SDK**
  - Attach attributes using native OpenTelemetry APIs in the active evaluation span context (commonly provided by `phoenix.otel` instrumentation).
  - Non-normative example:

    ```python
    # pseudo-code
    span.set_attribute("scm.eval.task_id", task_id)
    span.set_attribute("scm.eval.model_id", model_id)
    span.set_attribute("scm.eval.run_mode", run_mode)
    span.set_attribute("scm.eval.syntax_errors_caught", syntax_errors_caught)
    ```

- **LangGraph / LangChain**
  - Do NOT treat “manually grabbing the active span inside nodes” as a requirement.
  - Prefer attaching attributes via graph invocation metadata (e.g., `config={"metadata": {...}}`) so the framework’s instrumentation can map metadata to OpenTelemetry span attributes.
  - This is compatible with setups where a `LangChainInstrumentor` (via `phoenix.otel`) automatically parses LangChain metadata into span attributes.
  - Non-normative example:

    ```python
    # pseudo-code
    graph.invoke(
        inputs,
        config={
            "metadata": {
                "scm.eval.task_id": task_id,
                "scm.eval.model_id": model_id,
                "scm.eval.run_mode": run_mode,
                "scm.eval.syntax_errors_caught": syntax_errors_caught,
            }
        },
    )
    ```

## Non-goals
- The evaluator/orchestrator does NOT compute final answer correctness or score against ground truth.
- Accuracy scoring MUST happen in a separate LLM-as-a-judge repository to avoid benchmark data leakage.
- This evaluator only collects execution metrics and preserves raw model responses for downstream analysis.

## Validation checklist (doc-only)
- `outputs/evaluation_results.jsonl` row schema includes exactly: `task_id`, `model_id`, `run_mode`, `raw_response`, `execution_metrics`.
- `execution_metrics` includes exactly: `syntax_errors_caught`, `successful_retry_attempt`, `tools_called`.
- OpenTelemetry attribute keys match exactly: `scm.eval.task_id`, `scm.eval.model_id`, `scm.eval.run_mode`, `scm.eval.syntax_errors_caught`.
- Phoenix project name is referenced: `PHOENIX_PROJECT_NAME=scm-cert-eval-sandbox`.
