# Benchmark Data

This directory stores the golden benchmark prompt set used for task evaluation.

## Files

- `golden_tasks_questions_only.jsonl`: canonical benchmark input set, one JSON object per line.
- `metadata.info`: dataset schema and summary statistics.

## Dataset Summary

The current benchmark file contains 119 tasks.

Each record has exactly these four fields:

- `task_id` (string): stable task identifier.
- `scenario_context` (string): real-world logistics/supply chain context.
- `agent_prompt` (string): instruction prompt presented to the agent.
- `t_shirt_size` (string): complexity bucket (`S`, `M`, or `L`).

Data quality checks:

- All 119 records are valid JSON objects.
- Required fields are present for all records.
- No duplicate `task_id` values were found.

Complexity distribution:

- `S`: 17
- `M`: 49
- `L`: 53

Text-length profile (characters):

- `scenario_context`: min 424, max 1960, mean 835.76
- `agent_prompt`: min 335, max 2355, mean 1036.51

## Quick Validation

Use this command from the repository root to validate line count and parseability:

```bash
wc -l data/benchmark/golden_tasks_questions_only.jsonl
python3 -c "import json, pathlib; p=pathlib.Path('data/benchmark/golden_tasks_questions_only.jsonl'); [json.loads(x) for x in p.read_text().splitlines() if x.strip()]; print('ok')"
```

