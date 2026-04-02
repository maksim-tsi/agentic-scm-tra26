# Evaluators

Evaluator implementations live here. The goal is to expose a stable interface:

- `BaseEvaluator.evaluate(task_id: str) -> EvalResult`

## Evaluation Modes

- Naive baseline: zero-shot LLM reasoning without tool execution.
- Agentic treatment: YAAM-based agent endpoint expected to run with tool access.

## Current Modules

- `naive_llm_client.py` — OpenRouter (OpenAI-compatible) client skeleton.
- `agentic_mas_client.py` — HTTP client skeleton for the YAAM-based agent (DTR TBD).

## Current Status

- Client wiring and configuration scaffolding are in place.
- Benchmark loading, response scoring, and trace-linked metric computation are not yet implemented.
- DTR payload/trace schema remains to be finalized before end-to-end evaluator runs.

