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

