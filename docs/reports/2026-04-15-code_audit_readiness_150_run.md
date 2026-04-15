# Code Audit Readiness Report — 150-task Unattended Benchmark Run

Date: 2026-04-15  
Repo: `agentic-scm-tra26`

## Executive Summary

**Not ready** for a 150-task unattended benchmark run **as described** (“Naive LLMs vs Agentic MAS (YAAM)”), because:

- The benchmark dataset and loader are **questions-only** (no `expected_answer` / ground truth), and **this repo explicitly does not compute accuracy** against ground truth (by design). Any “Accuracy” comparison must come from a separate scoring/judge pipeline. (`docs/rfcs/002-execution-metrics-telemetry.md`, `docs/evaluation/contract.md`)
- The YAAM-based path (`src/evaluators/agentic_mas_client.py`) is **not wired into the orchestrator** and its evaluator is a **stub** (`NotImplementedError`). The same is true for the “naive evaluator” class in `src/evaluators/naive_llm_client.py`.
- The orchestrator can run the 150 questions through OpenRouter (with/without tools), but it has **observability + resilience gaps** that are risky for unattended runs (e.g., hard dependency on Phoenix tracing init; output JSONL drops error details and can drop raw responses on failures).

What *is* ready today: the `scripts/run_orchestrator.py` + `src/orchestrator_native_tool_calling.py` pipeline can produce RFC002-style JSONL rows with `raw_response` + `execution_metrics` for the RFC000 run modes **Naive / Naive+Evidence / Tools / Tools+Evidence**.

## Scope of Code Read

- `data/benchmark/golden_tasks_questions_only.jsonl` (first 3 rows inspected)
- `src/evaluators/naive_llm_client.py`
- `src/evaluators/agentic_mas_client.py`
- `src/utils/README.md` (only content present under `src/utils/`)
- `scripts/run_orchestrator.py`
- `src/orchestrator_native_tool_calling.py` (actual benchmark loader + execution loop)

## Hypothesis Verification (TRUE/FALSE with Proof)

### Hypothesis 1 — Ground Truth Blocker
**Claim:** The benchmark loading logic or JSONL contains `expected_answer` needed for mathematical Accuracy; if questions-only, accuracy may silently fail to 0.0.

**Verdict: TRUE (ground truth is absent); “silent 0.0” is not applicable because accuracy is not computed here.**

**Proof (questions-only enforced by loader):**

```py
# src/orchestrator_native_tool_calling.py:44-79
expected = {"task_id", "scenario_context", "agent_prompt", "t_shirt_size"}
...
keys = set(row.keys())
if keys != expected:
    raise ValueError(...)
```

This means the loader will **reject** any dataset row containing `expected_answer` (or any other extra key).

**Proof (contract explicitly questions-only):**

```md
# docs/evaluation/contract.md:3-11
Each JSONL row is an object with exactly these four keys:
- task_id
- scenario_context
- agent_prompt
- t_shirt_size
```

**Proof (accuracy scoring explicitly out-of-scope in this repo):**

```md
# docs/rfcs/002-execution-metrics-telemetry.md:117-120
- The evaluator/orchestrator does NOT compute final answer correctness or score against ground truth.
- Accuracy scoring MUST happen in a separate LLM-as-a-judge repository...
```

**Operational implication:** A 150-task run can generate raw responses, but any mathematical “Accuracy” KPI must be computed downstream (outside this repo).

---

### Hypothesis 2 — Soft Constraints & Resilience
**Claim:** If a smaller model returns malformed JSON or forgets `<FINAL_ANSWER>`, the code catches exceptions, preserves raw output, and continues; otherwise it crashes/discards output.

**Verdict: FALSE (it usually continues, but it does not reliably preserve raw output/error details on failure).**

**What the code does well (continues on tool-call JSON/validation problems):**

```py
# src/orchestrator_native_tool_calling.py:375-400
try:
    args_obj = json.loads(arg_str or "{}")
except json.JSONDecodeError as exc:
    messages.append({"role": "user", "content": f"Tool call arguments were not valid JSON for {tool_name}: {exc}"})
    continue
...
except ValidationError as exc:
    validation_errors_this_turn += 1
    messages.append({"role": "user", "content": _format_validation_error(exc, tool_name=tool_name)})
    continue
...
if validation_attempt >= MAX_VALIDATION_RETRIES:
    return "", ExecutionMetrics(...)
```

**What the code does not do (preserve raw response + error on exceptions):**

```py
# scripts/run_orchestrator.py:236-266
try:
    raw_response, metrics_obj = run_task(...)
except Exception as exc:
    failures += 1
    raw_response = ""
    execution_metrics = {"syntax_errors_caught": 0, "successful_retry_attempt": 0, "tools_called": []}
    span.set_attribute("scm.eval.error", f"{type(exc).__name__}: {exc}")

row = {
    "task_id": ...,
    "model_id": ...,
    "run_mode": ...,
    "raw_response": raw_response,
    "execution_metrics": execution_metrics,
}
_append_jsonl(..., row)
```

- The exception text is **not written to `outputs/evaluation_results.jsonl`** (only to a trace span attribute).
- `raw_response` is explicitly reset to `""` on exception, even though the provider may have returned partial text.
- Multiple “hard failure” paths inside `run_task` also return `""` (e.g., unknown tool name), which causes `raw_response` to be dropped.

**`<FINAL_ANSWER>` tag:** There is **no parsing requirement** for `<FINAL_ANSWER>` in the orchestrator pipeline; it returns “final answer as plain text”:

```py
# src/orchestrator_native_tool_calling.py:217-222
"Return the final answer as plain text."
```

**Operational implication:** The run is reasonably resilient to tool-call formatting failures, but unattended runs will produce “ERR” rows with empty `raw_response` and no error string in the JSONL, which weakens postmortems and downstream analysis.

---

### Hypothesis 3 — Trace Propagation (YAAM memory layer)
**Claim:** YAAM network calls inject `trace_id`/`traceparent` so traces connect end-to-end.

**Verdict: FALSE.**

**Proof (YAAM client builds headers without trace context):**

```py
# src/evaluators/agentic_mas_client.py:47-55
headers = {"Content-Type": "application/json"}
if self._config.api_key:
    headers["Authorization"] = f"Bearer {self._config.api_key}"
req = urllib.request.Request(self._config.url, data=body, headers=headers, method="POST")
```

There is no `traceparent` (W3C), `baggage`, or other trace header injection.

**Additional note:** The main orchestrator (`scripts/run_orchestrator.py`) does not call `YAAM_AGENT_URL` at all; the only reference to YAAM in `src/` is the unused evaluator client stub. (`src/evaluators/agentic_mas_client.py`)

---

### Hypothesis 4 — Ablation Matrix Implementation
**Claim:** The code supports the 4 run modes in `docs/rfcs/000-ablation-benchmark-matrix.md`, vs being hardcoded to one path.

**Verdict: TRUE (for RFC000’s v0 modes).**

**Proof (RunMode supports 4 choices):**

```py
# src/orchestrator_native_tool_calling.py:12
RunMode = Literal["Naive", "Naive+Evidence", "Tools", "Tools+Evidence"]
```

**Proof (CLI exposes `--run-mode` with those choices):**

```py
# scripts/run_orchestrator.py:82-87
parser.add_argument(
    "--run-mode",
    default="Tools",
    choices=list(get_args(RunMode)),
)
```

**Proof (RFC000 lists the same 4 modes):**

```md
# docs/rfcs/000-ablation-benchmark-matrix.md:37-42
1) Naive
2) Naive+Evidence
3) Tools
4) Tools+Evidence
```

**Important gap vs your stated “Agentic MAS / Full MAS”:** This repo’s ablation matrix is implemented as **tool-calling vs no-tools** (plus Evidence-table variant). A YAAM-based “Agentic MAS” path is not integrated into `scripts/run_orchestrator.py`, and the YAAM evaluator is stubbed.

## Model Configuration (Hardcoded vs Configured)

### Primary benchmark runner (150-task candidate)
`scripts/run_orchestrator.py`:

- Model ID: **required**, from `--model-id` or `OPENROUTER_MODEL`; no default model is hardcoded. (`scripts/run_orchestrator.py:99-102`)
- Provider endpoint: `OPENROUTER_BASE_URL` (defaults to `https://openrouter.ai/api/v1`). (`scripts/run_orchestrator.py:25-27`, `scripts/run_orchestrator.py:107-108`)
- Auth: `OPENROUTER_API_KEY` required. (`scripts/run_orchestrator.py:103-106`)

### Infra smoke test (not the benchmark runner)
`scripts/smoke_test_infra.py` hardcodes a model list:

```py
# scripts/smoke_test_infra.py:16-23
DEFAULT_MODELS = [
    "x-ai/grok-4.1-fast",
    "meta-llama/llama-3.1-8b-instruct",
    "deepseek/deepseek-v3.2",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
]
```

## Actionable Blockers (Changes Needed Before “Run”)

### Blocker A — Unattended run can’t start if Phoenix isn’t reachable
**Why:** tracing init errors abort the run.

```py
# scripts/run_orchestrator.py:202-207
try:
    tracer_provider = _init_tracing(config)
except Exception as exc:
    print(f"TRACING INIT ERROR: {exc}", file=sys.stderr)
    return 2
```

**Fix direction (today):**
- Make tracing optional (continue without tracing if init fails), or add a `--no-tracing` flag.
- Alternatively, ensure the Phoenix collector endpoint is always reachable for the full run.

### Blocker B — Output JSONL loses failure reasons and can lose raw outputs
**Why:** on exception, `raw_response=""` and the exception is only on the span; the JSONL row schema has no `error`.

```py
# scripts/run_orchestrator.py:248-266
raw_response = ""
...
row = {..., "raw_response": raw_response, ...}
```

**Fix direction (today):**
- Add `error` (string) to each JSONL row on failure, and preserve best-effort raw text when available.
- Consider also writing a lightweight per-task artifact under `outputs/` containing the final `messages` transcript for postmortems.

### Blocker C — “Agentic MAS (YAAM)” path is not implemented for benchmark runs
**Why:** both evaluator classes are stubs and the orchestrator doesn’t call YAAM.

```py
# src/evaluators/naive_llm_client.py:86-87
raise NotImplementedError("Benchmark loading and scoring not implemented yet.")

# src/evaluators/agentic_mas_client.py:86-87
raise NotImplementedError("DTR schema and scoring not implemented yet.")
```

**Fix direction (today):**
- If the intended comparison includes a YAAM-based MAS, implement a YAAM-backed run path (wire format + request/response schema + artifact capture) and integrate it into `scripts/run_orchestrator.py` (or add a new runner script).

### Blocker D — Trace headers not propagated to YAAM agent calls
**Why:** YAAM client sets only `Content-Type` + optional `Authorization`.

```py
# src/evaluators/agentic_mas_client.py:50-54
headers = {"Content-Type": "application/json"}
...
```

**Fix direction (today):**
- Add W3C trace context propagation (`traceparent`, optionally `baggage`) pulled from the current OpenTelemetry context when making the HTTP request.

## Notes / Sanity Checks Observed

- Tool registry is strict about Pydantic I/O schemas; for this repo state, `uv run python scripts/bootstrap_active_tools.py --check` passes and `tools.ACTIVE_TOOLS` imports successfully (35 tools).
- `src/utils/` contains placeholders only; no metric parsing/scoring logic exists yet. (`src/utils/README.md:8`, `src/utils/README.md:22-24`)

