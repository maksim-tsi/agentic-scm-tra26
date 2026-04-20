# 2026-04-20 Medium Batch Initial Results

## Scope

Analysis of current artifacts under outputs/batches for the 6 baseline models after runtime model override fix.

Benchmark denominator: 119 tasks

## Per-Model Summary

| Model | Progress (unique tasks) | Rows | OK Rows | ERR Rows | Debug Rows | model_id Mismatch Rows | Top model_id values | Notes |
|---|---:|---:|---:|---:|---:|---:|---|---|
| x-ai/grok-4.1-fast | 76/119 | 76 | 71 | 5 | 5 | 0 | x-ai/grok-4.1-fast (76) | ok |
| meta-llama/llama-3.1-8b-instruct | 19/119 | 19 | 4 | 15 | 15 | 0 | meta-llama/llama-3.1-8b-instruct (19) | ok |
| deepseek/deepseek-v3.2 | 7/119 | 7 | 7 | 0 | 0 | 0 | deepseek/deepseek-v3.2 (7) | ok |
| google/gemini-2.5-flash-lite | 0/119 | 0 | 0 | 0 | 0 | 0 | - | missing evaluation_results.jsonl |
| openai/gpt-oss-120b | 0/119 | 0 | 0 | 0 | 0 | 0 | - | missing evaluation_results.jsonl |
| openai/gpt-oss-20b | 0/119 | 0 | 0 | 0 | 0 | 0 | - | missing evaluation_results.jsonl |

## Key Findings

- No model_id mismatches detected in current evaluation_results.jsonl rows.
- Models with no completed tasks yet:
  - google/gemini-2.5-flash-lite
  - openai/gpt-oss-120b
  - openai/gpt-oss-20b
- Aggregate completed task slots across model runs: 102 (sum across model folders).

## Recommended Next Steps

1. Continue 20-task batches for models with lowest progress until all models reach comparable coverage.
2. Watch debug JSONL growth; if ERR rows rise, triage by error_type from evaluation_results_debug.jsonl.
3. Re-run this report after each batch wave to track parity and model routing integrity.

