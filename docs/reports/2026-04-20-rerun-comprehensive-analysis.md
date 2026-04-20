# 2026-04-20 Rerun Comprehensive Analysis

## 1. Executive Summary

This report analyzes rerun artifacts across 6 baseline models using JSONL outputs, LangGraph checkpoints, and Phoenix traces (best effort). Aggregate completed task slots: 213 over benchmark denominator 119.

## 2. Data Sources and Method

- Per-model outcomes: outputs/batches/*/evaluation_results.jsonl
- Per-model errors: outputs/batches/*/evaluation_results_debug.jsonl
- Attempt telemetry: outputs/langgraph_checkpoints.sqlite
- Trace correlation: Phoenix spans via trace_id when available
- Language detection: heuristic classifier (English markers + script detection)

## 3. Run Coverage and Progress Matrix

| Model | Unique Tasks | Rows | OK Rows | Empty Rows | Debug Rows | Delta vs 2026-04-20 Initial | model_id Mismatch |
|---|---:|---:|---:|---:|---:|---:|---:|
| x-ai/grok-4.1-fast | 96/119 | 96 | 89 | 7 | 7 | +20 | 0 |
| meta-llama/llama-3.1-8b-instruct | 39/119 | 39 | 4 | 35 | 35 | +20 | 0 |
| deepseek/deepseek-v3.2 | 22/119 | 22 | 20 | 2 | 2 | +15 | 0 |
| google/gemini-2.5-flash-lite | 20/119 | 20 | 12 | 8 | 8 | +20 | 0 |
| openai/gpt-oss-120b | 18/119 | 18 | 11 | 7 | 7 | +18 | 0 |
| openai/gpt-oss-20b | 18/119 | 18 | 11 | 7 | 7 | +18 | 0 |

## 4. Reliability and Error Taxonomy

Global error_type frequency:
- GraphRecursionError: 52
- ValidationError: 12
- RuntimeError: 2

Per-model dominant errors:
- x-ai/grok-4.1-fast: ValidationError (6), RuntimeError (1)
- meta-llama/llama-3.1-8b-instruct: GraphRecursionError (35)
- deepseek/deepseek-v3.2: GraphRecursionError (2)
- google/gemini-2.5-flash-lite: GraphRecursionError (7), ValidationError (1)
- openai/gpt-oss-120b: GraphRecursionError (4), ValidationError (3)
- openai/gpt-oss-20b: GraphRecursionError (4), ValidationError (2), RuntimeError (1)

Error signature families (message-level):
- pydantic_validation: 12
- json_structure_or_parse: 6

## 5. Attempts, Retries, and Loop Dynamics (LangGraph)

- Checkpoint max rowid: 12751
- Tasks with at least one attempted thread: 96
- Attempts per task (min/median/max): 1/3.0/15
- Thread loop depth proxy (min/median/max): 2/7.0/8525
- Attempted threads by model_id from checkpoint metadata:
  - x-ai/grok-4.1-fast: 225
  - meta-llama/llama-3.1-8b-instruct: 40
  - deepseek/deepseek-v3.2: 29
  - google/gemini-2.5-flash-lite: 20
  - openai/gpt-oss-120b: 20
  - openai/gpt-oss-20b: 20
- Threads with retrieved_context channel writes (YAAM L3 path evidence): 353

## 6. Tool and YAAM Utilization

| Model | Total Tool Calls | Unique Tools | Avg Tools/Row |
|---|---:|---:|---:|
| x-ai/grok-4.1-fast | 138 | 21 | 1.44 |
| meta-llama/llama-3.1-8b-instruct | 17 | 4 | 0.44 |
| deepseek/deepseek-v3.2 | 37 | 15 | 1.68 |
| google/gemini-2.5-flash-lite | 29 | 14 | 1.45 |
| openai/gpt-oss-120b | 8 | 5 | 0.44 |
| openai/gpt-oss-20b | 8 | 6 | 0.44 |

YAAM evidence levels:
- Proven used: retrieved_context channel writes observed in LangGraph writes table.
- Trace evidence unavailable due to Phoenix access/query limitations.

## 7. Phoenix Trace Correlation

- Phoenix status: error
- Trace coverage (matched trace_ids / observed trace_ids): 0/66
- Matched spans: 0
- Tool-signature spans: 0
- YAAM-signature spans: 0
- Phoenix query notes:
  - phoenix query failed: ConnectError: [Errno -2] Name or service not known

## 8. Output Language Characteristics

| Model | Dominant Language | Non-English Rows |
|---|---|---:|
| x-ai/grok-4.1-fast | english | 4 |
| meta-llama/llama-3.1-8b-instruct | empty | 0 |
| deepseek/deepseek-v3.2 | english | 0 |
| google/gemini-2.5-flash-lite | english | 0 |
| openai/gpt-oss-120b | english | 2 |
| openai/gpt-oss-20b | english | 0 |

## 9. Key Findings with Confidence

- Routing integrity: no model_id mismatches detected (high confidence from JSONL).
- High-error lanes: meta-llama/llama-3.1-8b-instruct (high confidence from debug JSONL).
- Loop/attempt dynamics measured from checkpoints (medium-high confidence; metadata decode dependent).
- Trace linkage not available (low confidence for span-level latency claims).

## 10. Threats to Validity and Gaps

- Success proxy uses non-empty raw_response; this does not equal correctness against ground truth.
- Language classification is heuristic and may undercount nuanced bilingual outputs.
- YAAM L2/L4 success/failure is only partially observable from current artifacts.
- Phoenix spans may be incomplete due to retention/query windows and endpoint availability.

## 11. Recommendations

1. Add structured YAAM operation result logging (success/failure + endpoint + latency) to JSONL artifacts.
2. Add explicit attempt index and per-task retry counters to output rows for direct attempt analytics.
3. Add normalized error signature extraction in pipeline to compare model reliability longitudinally.
4. Add span attributes for node-level latency (planner/executor/finalizer) for publication-grade timing analysis.

## 12. Reproducibility

- Script: scripts/adhoc/comprehensive_rerun_analysis.py
- Baseline comparison: docs/reports/2026-04-20-medium-batch-initial-results.md
- Inputs: outputs/batches/*, outputs/langgraph_checkpoints.sqlite, data/benchmark/golden_tasks_questions_only.jsonl
