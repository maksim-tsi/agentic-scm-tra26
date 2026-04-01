# Evaluators

Evaluator implementations live here. The goal is to expose a stable interface:

- `BaseEvaluator.evaluate(task_id: str) -> EvalResult`

Stubs included:

- `naive_llm_client.py` — OpenRouter (OpenAI-compatible) client skeleton.
- `agentic_mas_client.py` — HTTP client skeleton for the YAAM-based agent (DTR TBD).

