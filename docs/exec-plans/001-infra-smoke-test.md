# Execution Plan 001 — Infra Smoke Test (OpenRouter + Phoenix)

## Purpose
Validate that our two critical external dependencies are operational before implementing the full evaluator pipeline:

1) **OpenRouter API** (LLM gateway) can be reached and can serve our target benchmark models.
2) **Arize Phoenix** (self-hosted on `skz-dev-lv`) can receive and store **OpenTelemetry / OpenInference** traces for OpenAI-SDK-compatible calls.

Success criteria:

- For each default model, the script receives the exact text `SCM-INFRA-OK`.
- Phoenix contains a trace in project `PHOENIX_PROJECT_NAME` with:
  - a parent span named `scm.infra_smoke_test` containing our `scm.eval.*` attributes, and
  - a child auto-instrumented LLM span whose output contains `SCM-INFRA-OK`.

## Preconditions
- Python 3.12+
- Dependencies installed (recommended):
  - `uv sync --dev --frozen`
  - The repo uses `uv.lock` as the source of truth.
- Environment configured via `.env` (copied from `.env.example`).

### Required environment variables
OpenRouter:
- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)

Phoenix (self-hosted):
- `DEV_NODE_IP` (used to construct collector/base URLs; **not localhost**)
- `PHOENIX_PORT` (default 6006 in `.env.example`)
- `PHOENIX_COLLECTOR_ENDPOINT` (example: `http://${DEV_NODE_IP}:6006/v1/traces`)
- `PHOENIX_PROJECT_NAME` (default: `scm-cert-eval-sandbox`)

Optional (if Phoenix requires auth):
- `PHOENIX_API_KEY`
- `PHOENIX_CLIENT_HEADERS`

## Steps (A–E)

### Step A — Environment setup
The smoke test loads variables from `.env` via `python-dotenv`.

Important:
- The Phoenix collector endpoint MUST point to `${DEV_NODE_IP}`, not `localhost`.
- The script resolves `PHOENIX_BASE_URL` for REST queries by stripping `/v1/traces` from `PHOENIX_COLLECTOR_ENDPOINT` (or building `http://${DEV_NODE_IP}:${PHOENIX_PORT}`).

### Step B — OTel initialization (Phoenix + OpenInference)
The script calls `phoenix.otel.register(...)` with:
- `endpoint=PHOENIX_COLLECTOR_ENDPOINT`
- `project_name=PHOENIX_PROJECT_NAME`
- `auto_instrument=True`

This MUST enable OpenInference auto-instrumentation for the OpenAI Python SDK (and therefore OpenRouter, which is OpenAI-compatible).

### Step C — OpenRouter invocation (OpenAI SDK)
For each model, the script sends:

Prompt:
> Respond with exactly the text 'SCM-INFRA-OK' and nothing else.

Assertion:
- `content.strip() == "SCM-INFRA-OK"`

### Step D — Trace attribution (custom `scm.eval.*` without bypassing auto-instrumentation)
The script wraps each OpenAI SDK call in a manual *parent span* named `scm.infra_smoke_test` and sets:
- `scm.eval.task_id = "smoke_test_001"` (or the provided `--task-id`)
- `scm.eval.run_mode = "Naive"`
- `scm.eval.model_id = <model>`

The OpenAI SDK call MUST still be auto-instrumented by OpenInference, producing a child LLM span under this parent span.

### Step E — Validation & REST API refinement loop (Phoenix query)
The script waits briefly, flushes exporters, then polls Phoenix via `phoenix.client.Client` to assert:

1) A **parent span** exists with our `scm.eval.task_id` and expected `scm.eval.model_id/run_mode`.
2) In the **same trace**, a **child LLM span** exists whose output contains `SCM-INFRA-OK`.

#### Why Step E exists (Refinement Loop)
By querying the Phoenix API programmatically, we give the Coding Assistant the ability to verify its own OTel instrumentation.

In future complex development, if an agent run fails, the assistant can query the Phoenix REST API to retrieve:
- the exact span tree,
- error status/messages,
- prompt/response context captured by auto-instrumentation,

and debug the issue without human intervention (trace-driven refinement loop).

## How to run
Default model list (benchmark target set):

- `x-ai/grok-4.1-fast`
- `meta-llama/llama-3.1-8b-instruct`
- `deepseek/deepseek-v3.2`
- `google/gemini-2.5-flash-lite`
- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`

```bash
uv run python scripts/smoke_test_infra.py
```

Single model:

```bash
uv run python scripts/smoke_test_infra.py --model x-ai/grok-4.1-fast
```

## Expected output
- One PASS/FAIL line per model.
- Non-zero exit code if any model fails OpenRouter connectivity or Phoenix trace validation.
