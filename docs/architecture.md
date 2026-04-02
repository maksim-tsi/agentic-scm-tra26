# Architecture and boundaries

## High-level architecture
This repo has two primary evaluation targets:

1) **Naive baseline**: an LLM is prompted to answer without tool execution.
2) **Agentic MAS**: an external agent endpoint executes with access to deterministic SCM tools.

Core pieces:
- `data/benchmark/` provides **questions-only** benchmark inputs (JSONL).
- `tools/` provides deterministic, typed SCM skills (Pydantic v2 strict models).
- `src/evaluators/` wires clients and defines the evaluator interface (`EvalResult`).
- `tests/` enforces mechanical invariants so agents can safely iterate.

## Read-only / versioned policies (reproducibility)
To keep evaluations reproducible:

- `data/benchmark/golden_tasks_questions_only.jsonl` is **immutable** for a given benchmark version.
  - If changes are needed, create a versioned dataset artifact (new filename / directory) and update docs/metadata.
- `tools/` is treated as a **benchmarked tool surface**.
  - Avoid changing tool behavior silently.
  - If a tool must change, prefer adding a new versioned tool/module and updating the active registry deliberately.

## Outputs and artifacts
- Write runtime outputs to `outputs/` (gitignored except `outputs/README.md`).
- Never write generated files into `data/benchmark/`.

## Dependency management
- Source of truth for dependencies is `pyproject.toml` + `uv.lock`.
- `requirements.txt` is a fallback for users who cannot use `uv`.

## Dynamic Tool Retrieval (DTR) Policy
At the current stage, the evaluation harness uses a **golden registry** of deterministic SCM tools exported via `tools.ACTIVE_TOOLS` (currently 35 tools as of 2026-04-02).

### Why no vector search (yet)?
Using a vector DB (e.g., Qdrant) to retrieve a subset of tools is **overkill** at this scale:

- Modern model context windows can comfortably fit 35 JSON schemas without meaningful performance degradation.
- A fixed allowlist reduces complexity and increases reproducibility.

### Current DTR implementation (v0)
DTR is implemented as **full tool-schema injection**:

- Orchestrator constructs OpenAI-style tool schemas for every tool in `tools.ACTIVE_TOOLS`.
- Orchestrator passes the entire schema list into the model API call via the `tools` parameter.
- No retrieval, ranking, or tool filtering is performed.

### Future trigger
Revisit vector-search DTR only when the tool surface grows enough to pressure context size, latency, or model tool-selection reliability.
