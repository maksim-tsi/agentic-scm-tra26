# SCM-MAS Evaluation Framework (TRA 2026)

Evaluation harness for comparing **zero-shot “naive” LLMs** (via OpenRouter) against our **agentic MAS** that combines **YAAM memory** and **Skill Factory tools**, with support for **DTR**-style execution/tracing.

The current runnable path is the **native tool-calling orchestrator** (`scripts/run_orchestrator.py` + `src/orchestrator_native_tool_calling.py`) implementing:
- **RFC 001**: strict native tool-calling loop (Pydantic boundary; no code execution).
- **RFC 002**: strict per-task JSONL output + required Phoenix/OpenTelemetry span attributes.
- **Telemetry hardening**: W3C trace propagation into provider calls + “1 Task = 1 Session” mapping via `session.id`.
- **Resilience**: dual JSONL outputs (`evaluation_results.jsonl` + `evaluation_results_debug.jsonl`) and optional tracing.

## Architecture Theory

- **YAAM (Yet-Another Agent Memory):** persistent memory layer used by the Agentic MAS during task execution.
- **Skill Factory:** curated tool library (Python skills) used by the Agentic MAS to ground actions in deterministic capabilities.

## Evaluation Targets

1. **Zero-shot Naive LLMs** (e.g., Gemma, Llama 3, Mistral via OpenRouter).
2. **Agentic MAS** (YAAM-based + DTR + SCM Skills).

## Benchmarks

- **SCM-Cert-Bench (119 verified tasks):** TODO (add public link).

## Repository Layout

- `tools/` — Python skills imported from Skill Factory.
- `data/benchmark/` — golden benchmark tasks (JSON/JSONL) + metadata.
- `src/evaluators/` — evaluation clients and runner logic (naive vs agentic).
- `src/orchestrator_native_tool_calling.py` — RFC001 native tool-calling runner.
- `scripts/run_orchestrator.py` — RFC002 benchmark CLI runner (JSONL + tracing).
- `outputs/` — runtime logs, JSON reports, and YAAM memory dumps (not committed).

## Tool Catalog And Discovery

The `tools/` package currently exports active skills through `tools.ACTIVE_TOOLS`.
This is the runtime registry used by the agentic path.

Properties of the current tool set:

- Deterministic, in-process Python functions.
- Pydantic-based typed inputs/outputs in each module.
- No filesystem or network side effects inside tools.

For the full catalog and category breakdown, see `tools/README.md`.

## Read-Only Assets In This Workflow

For evaluation consistency, treat these assets as read-only:

- Tool implementations under `tools/`.
- Benchmark questions file `data/benchmark/golden_tasks_questions_only.jsonl`.

Documentation can evolve, but benchmark question content and imported tool logic should stay fixed unless you intentionally version a new benchmark/tool release.

## Setup

### Requirements

- Python **3.12+** (see `.python-version`)
- `uv` (recommended) or `pip`

### Install (recommended: uv)

```bash
uv sync --dev --frozen
```

### Install (fallback: venv + pip)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables

- `OPENROUTER_API_KEY` (required for naive LLM target)
- `PYTHONPATH=src:tools` (recommended for local imports)

Optional (depending on what you run):

- `OPENROUTER_MODEL`
- `OPENROUTER_BASE_URL`
- `YAAM_AGENT_URL`
- `YAAM_AGENT_API_KEY`

Phoenix / OpenTelemetry (optional; used when tracing is enabled):

- `PHOENIX_PROJECT_NAME` (default: `scm-cert-eval-sandbox`)
- `PHOENIX_COLLECTOR_ENDPOINT` (optional; if not set, the runner builds it from `DEV_NODE_IP` and `PHOENIX_PORT`)
- `DEV_NODE_IP` (only required when tracing is enabled and `PHOENIX_COLLECTOR_ENDPOINT` is not set)
- `PHOENIX_PORT` (default: `6006`, only used for endpoint construction)
- `PHOENIX_API_KEY` (optional; used for auth when provided)
- `PHOENIX_CLIENT_HEADERS` (optional; comma-separated `k=v` pairs; `Authorization=Bearer ...` is auto-added when `PHOENIX_API_KEY` is set)

Create a local `.env` from the template:

```bash
cp .env.example .env
```

## Run the orchestrator (RFC001 + RFC002)

The primary entry point is:
- `uv run python scripts/run_orchestrator.py`

Common examples:

```bash
# Full run (with tracing if Phoenix is configured)
uv run python scripts/run_orchestrator.py --model-id x-ai/grok-4.1-fast --run-mode Tools

# Single task (useful for debugging)
uv run python scripts/run_orchestrator.py --model-id x-ai/grok-4.1-fast --run-mode Tools --task-id task_00123

# Disable tracing entirely (still writes JSONL)
uv run python scripts/run_orchestrator.py --no-tracing --model-id x-ai/grok-4.1-fast --run-mode Tools
```

### Outputs

- `outputs/evaluation_results.jsonl`
  - **Strict RFC-002 schema** (exact keys: `task_id`, `model_id`, `run_mode`, `raw_response`, `execution_metrics`)
  - **Row-aligned**: always writes exactly 1 row per evaluated task; on exceptions it writes a safe fallback row (`raw_response=""`, zeroed `execution_metrics`) so downstream consumers stay index-aligned.
- `outputs/evaluation_results_debug.jsonl`
  - Written **only on exceptions** and contains rich postmortem details (`error_message`, `traceback`, `partial_raw_response`, etc.).

### Telemetry (Phoenix)

When tracing is enabled, each task runs under an OpenTelemetry span `scm.eval.task` with RFC-002 attributes (`scm.eval.*`), plus:
- `session.id = "task-<task_id>"` (strict “1 Task = 1 Session” mapping for Phoenix session filtering)
- Provider-side trace propagation: the runner injects the current W3C `traceparent` into OpenRouter calls via `extra_headers` (best-effort; falls back safely if the SDK doesn’t support `extra_headers`).
