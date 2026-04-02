# Evaluation contract

## Benchmark input schema (questions-only)
The canonical input set is `data/benchmark/golden_tasks_questions_only.jsonl`.

Each JSONL row is an object with **exactly these four keys**:
- `task_id` (string)
- `scenario_context` (string)
- `agent_prompt` (string)
- `t_shirt_size` (string: `S` | `M` | `L`)

## Evaluator interface (current)
Evaluators implement:
- `BaseEvaluator.evaluate(task_id: str) -> EvalResult`

`EvalResult` (see `src/evaluators/base.py`) contains:
- `passed` (bool): whether the run met the evaluation criterion (when scoring is implemented)
- `raw_output` (str | None): raw model/agent output (always preserve when available)
- `error` (str | None): error message on failure
- `metrics` (dict): numeric and categorical metrics (accuracy, format adherence, etc.)
- `artifacts` (dict): references to saved files under `outputs/`

## What gets scored (now vs later)
Current evaluator implementations are scaffolding. The contract below is for harness legibility:

- Always preserve **raw outputs**, even if they violate formatting guidelines.
- Formatting conventions (e.g. `<FINAL_ANSWER>...</FINAL_ANSWER>`) are **soft** constraints:
  - Do not fail the run solely due to formatting.
  - Track format adherence as a metric during evaluation.

## Artifact policy
- Default artifact root: `outputs/`
- Store:
  - logs
  - JSON reports
  - trace exports / dumps
  - agent memory dumps (if any)

