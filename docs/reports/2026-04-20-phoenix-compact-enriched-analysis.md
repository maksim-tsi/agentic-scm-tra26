# 2026-04-20 Phoenix Compact Enriched Analysis

## Executive Summary
This report enriches prior batch analysis using compacted Phoenix trace artifacts for project `agentic-scm-tra26` on `2026-04-20`. We processed all 1600 trace records from the compact dataset and built a selective deep-dive shortlist from anomaly buckets. The dominant observed error family in this corpus is schema/validation-related (Pydantic validation), with limited evidence of provider-side rate-limit behavior in the shortlisted traces.

## Inputs and Method
- Primary compact corpus: `outputs/phoenix_traces_2026-04-20_compact.jsonl`
- Compact summary: `outputs/phoenix_traces_2026-04-20_compact_summary.json`
- Aggregated metrics (this run): `outputs/phoenix_traces_2026-04-20_metrics_summary.json`
- Selective shortlist (this run): `outputs/phoenix_traces_2026-04-20_selective_shortlist.json`
- Raw source for targeted grep: `outputs/phoenix_traces_2026-04-20_analyst_raw.jsonl`

Method:
1. Aggregate compact traces into model/run/error/signal distributions.
2. Build selective anomaly shortlist (per-bucket) for manual evidence extraction.
3. Run constrained grep-like search on raw traces only for shortlisted trace IDs and explicit signatures (`pydantic|validation|json invalid|rate limit|429|openrouter|graphrecursionerror`).
4. Reconcile compact-level counts with selective evidence findings.

## Corpus Snapshot
- Total traces analyzed: 1600
- Status distribution: all `ok` in compact records
- Unique shortlisted traces for deep-dive: 16

## Aggregate Findings From Compact Metrics
From `outputs/phoenix_traces_2026-04-20_metrics_summary.json`:

- Error category distribution (top):
  - `provider_api`: 1441
  - `pydantic_validation`: 1163
  - `recursion`: 52
  - `rate_limit_429`: 44
  - `json_structure`: 3

- Signal-positive traces:
  - YAAM signal positive: 124
  - Tool signal positive: 1441
  - Error signal positive: 1368

Interpretation:
- The corpus is heavily tool/error-instrumented.
- Validation/schema pressures are a primary failure mode.
- YAAM-related signals are present but not universal across traces.

## Selective Deep-Dive (Scoped Raw Search)
Targeting only shortlisted trace IDs:
- Signature counts in shortlisted subset:
  - `pydantic`: 10
  - `validation`: 10
  - `json invalid`: 1
  - `rate limit`: 0
  - `429`: 0
  - `openrouter`: 0
  - `graphrecursionerror`: 0

Observations:
1. The selected anomaly subset is predominantly validation-centric.
2. No direct provider-rate-limit or OpenRouter-error signatures were found in this shortlist scan.
3. No direct recursion signature was found in this shortlist subset, despite nonzero recursion category counts in aggregate compact metrics.

## Reconciliation Notes
- Aggregate compact metrics include `rate_limit_429` and `recursion` categories, but the selective shortlist scan did not surface those signatures in the sampled subset.
- This is expected when shortlist buckets prioritize different anomaly slices than global maxima.
- Recommended follow-up: run a second selective shortlist specifically seeded from traces tagged `rate_limit_429` and `recursion` in compact rows.

## Practical Conclusion
For the current enriched analysis pass:
1. We already have sufficient compacted Phoenix information to proceed without third-party per-trace analysts for core quantitative reporting.
2. The highest-confidence claim is validation/schema instability dominance in sampled anomalies.
3. Provider-rate-limit and recursion claims should be reported with medium confidence unless corroborated by targeted secondary shortlist evidence.

## Recommended Next Steps
1. Create two additional focused shortlists:
   - Traces with nonzero `rate_limit_429` category
   - Traces with nonzero `recursion` category
2. Repeat selective raw evidence extraction for those shortlists only.
3. Merge findings into the master rerun report:
   - `docs/reports/2026-04-20-rerun-comprehensive-analysis.md`
4. Preserve reproducibility artifacts as-is under `outputs/`.

## Threats to Validity
- Compact error categories are heuristic extractions from span text/signals and may over-approximate provider-related labels.
- Selective grep is intentionally narrow and may miss semantically equivalent error strings not in the signature set.
- Confidence should remain tied to direct evidence counts and shortlist scope.

## Focused Pass: Recursion and 429 Forensics

This section adds a targeted pass over recursion- and 429-tagged traces using:
- `scripts/adhoc/extract_phoenix_focused_evidence.py`
- `outputs/phoenix_traces_2026-04-20_focused_evidence.json`
- `outputs/phoenix_traces_2026-04-20_analyst_raw.jsonl`

### Scope and Checks
- Focused extractor selection: 30 recursion traces + 30 rate-limit traces (60 total analyzed).
- Additional raw probe for 429 classification:
  - Unique traces containing `429`: 93
  - Sampled for deeper classification: 30 traces
  - Provider-429 evidence in sampled traces: 0
  - Validation/Pydantic evidence in sampled traces: 20
  - GraphRecursionError overlap in sampled 429 traces: 0

### Key Evidence
Recursion bucket (sampled 20 from recursion IDs via raw probe):
- `span_count` distribution: `{1: 20}`
- Unique span names: `scm.eval.task`
- Unique span kinds: `UNKNOWN`
- Recurring error text on span attributes:
  - `GraphRecursionError: Recursion limit of 30 reached without hitting a stop condition...`

Rate-limit bucket (429-focused raw probe):
- The strongest repeated text pattern is validation-instruction content (for example, lines containing guidance like `If a tool returns a validation error (Pydantic), analyze the error...`).
- No direct provider throttle indicators were detected in the sampled 429 traces (`provider_api_error`, `http 429`, `too many requests`, `x-ratelimit` all absent in sample).

### Root Cause Statement (Llama 3.1 Recursion Loops)
Most `meta-llama/llama-3.1-8b-instruct` recursion failures in this Phoenix corpus are observed only as terminal evaluator-level error spans (`scm.eval.task`) with no captured internal node/tool trace chain. Therefore, the logs support a high-confidence claim that the run exceeded LangGraph step limits, but only medium confidence on the exact internal loop mechanics from Phoenix alone.

Practical interpretation:
1. The immediate trigger is deterministic: recursion limit reached before a stop condition.
2. The likely underlying mechanism is repeated non-terminating planner/executor cycling, but this is not directly observable in these traces because the instrumentation appears truncated to the eval boundary for recursion cases.
3. For 429-tagged traces, many labels are contamination from generic error text heuristics rather than verified provider throttling events.

### Confidence
- High confidence: recursion-limit trip itself, evaluator-level failure signature, and weak provider-429 evidence in sampled 429 traces.
- Medium confidence: exact internal state-machine loop path for Llama 3.1 (requires deeper node-level tracing/checkpoint event replay to prove conclusively).

## Checkpoint Reconstruction: Definitive Loop Mechanics

To close the Phoenix observability gap, we reconstructed Llama recursion behavior directly from `outputs/langgraph_checkpoints.sqlite` writes/checkpoints:
- Script: `scripts/adhoc/extract_checkpoint_recursion_loops.py`
- Output artifact: `outputs/llama_recursion_checkpoint_loops.json`
- Scope: 3 sampled threads for `meta-llama/llama-3.1-8b-instruct`, last 20 writes per thread.

### What the Loop Actually Looks Like
Across sampled recursion threads, the same ping-pong structure appears:
1. `messages` alternates between an empty message payload and contradictory or non-progress natural-language answer text.
2. Control alternates between `branch:to:executor` and `branch:to:executor_tools`.
3. The loop does not stabilize to a terminating condition before recursion depth is exhausted.

Observed channel totals across sampled loops:
- `messages`: 30
- `branch:to:executor`: 15
- `branch:to:executor_tools`: 15

Representative thread evidence:
- `workcenter_load_calculation_bremerhaven_001_3c9b7a4f`
  - Alternates between:
    - empty message payload (`b'\\x90'`)
    - `The final answer is $\\boxed{1500}$.`
    - `There is no final answer to this problem as it is a calculation.`
- `MPS_PAB_Calc_Rotterdam_2025H1_aa91d341`
  - Repeats empty message payload followed by `The final answer is 0.` then cycles again.
- `SC_CSL_001_79a94fd2`
  - Repeats empty message payload followed by non-progress meta text (`There is no need to repeat the same response...`) and loops.

### Definitive Root Cause
The recursion loop is primarily a control-flow non-convergence pattern, not a provider-429 failure:
1. The agent emits unstable/contradictory terminal-style content in `messages`.
2. The graph keeps routing between executor and executor_tools branches despite no net progress.
3. Empty message payloads (`b'\\x90'`) repeatedly re-enter the cycle, preventing stop-condition satisfaction.

In short: the 30-step `GraphRecursionError` is caused by repeated executor <-> executor_tools re-entry with oscillating or empty agent messages, not a deterministic external API throttle event.
