# sc_ra_001 Evidence Drop Analysis

Date: 2026-04-16

## Executive Summary
The evidence pipeline failed for two concrete reasons observed in trace data:

1. In the first invocation segment, the Executor called the Kraljic tool and received a valid categorical result, but did not call store_intermediate_fact before emitting FINAL_EXECUTION_DONE.
2. In the latest invocation segment, the Executor did not call any tool at all and still emitted FINAL_EXECUTION_DONE.

As a result, no L2 working-memory facts were available for the Finalizer, and the final response was generated without an evidence table.

A secondary architectural issue was found: repeated orchestrator runs reused the same thread id sc_ra_001 with checkpoint persistence, causing cross-run message accumulation in one thread history. This makes behavior drift across reruns and complicates deterministic diagnosis.

## Artifacts Used
- LangGraph checkpoint database: outputs/langgraph_checkpoints.sqlite
- Diagnostic extractor script: scripts/debug_trace_sc_ra_001.py
- Diagnostic output: outputs/debug_trace_sc_ra_001.json
- Output row: outputs/evaluation_results.jsonl

## Trace Timeline
The latest checkpoint contains two invocation segments for the same thread id.

### Segment 0 (message indices 0-4)
- Message 0: User task prompt.
- Message 1: Executor plan text.
- Message 2: Assistant tool_call to kraljic_matrix__kraljic_supply_matrix_classification with arguments:
  - profit_impact: high
  - supply_risk: high
- Message 3: Tool output returned:
  - item_classification: strategic
  - procurement_strategy: Risk mitigation through long-term partnerships...
  - profit_impact: high
  - supply_risk: high
- Message 4: Assistant emitted FINAL_EXECUTION_DONE without any store_intermediate_fact tool call.

Observation:
- store_intermediate_fact_calls is empty.
- This is the exact point where evidence propagation to L2 should have happened but did not.

### Segment 1 (latest invocation, message indices 5-10)
- Message 5: User task prompt repeated.
- Messages 6-9: Assistant text-only reasoning and answers.
- Message 10: Assistant emitted FINAL_EXECUTION_DONE: Threat.

Observation:
- No tool calls at all in the latest segment.
- No store_intermediate_fact calls.
- Latest segment therefore produced no tool-grounded artifacts for Finalizer evidence construction.

## Phoenix Integration Findings (Best Effort)
Phoenix endpoint was reachable at http://127.0.0.1:6006, but the server version is 12.14.2 and does not support the traces route needed by the current client for direct session trace retrieval.

What was still extracted:
- Candidate spans for scm.eval.task with attributes including:
  - scm.eval.task_id: sc_ra_001
  - scm.eval.model_id: x-ai/grok-4.1-fast
  - scm.eval.run_mode: AgenticGraph

What could not be extracted:
- Finalizer input prompt payload (including the exact YAAM L2 Facts blob) was not recoverable from available span payloads on this server/version combination.

Practical implication:
- We cannot directly prove the exact L2 blob text from Phoenix in this run.
- However, the LangGraph trace proves no store_intermediate_fact calls occurred, so L2 would be expected to be empty for facts originating from this execution.

## Root Cause Analysis
Primary root cause:
- Prompt-only enforcement is insufficient. The Executor can ignore the mandatory storage instruction and still progress by emitting FINAL_EXECUTION_DONE.

Secondary root cause:
- The graph/router has no hard state gate that requires store_intermediate_fact success after tool execution before allowing completion.

Tertiary root cause:
- Thread reuse with persistent checkpoints (same thread id per rerun) causes cross-run message carryover. This introduces non-deterministic behavior on rerun and can suppress tool usage in later invocations.

## Proposed Fix (Architectural Enforcement)
1. Enforce storage as a graph-level gate, not a prompt preference.
- Add explicit state flags, for example:
  - non_memory_tool_called
  - l2_store_confirmed
- Set non_memory_tool_called true when any deterministic SCM tool is called.
- Set l2_store_confirmed true only on successful ToolMessage result from store_intermediate_fact.
- Block transition to finalizer unless either:
  - no tool was used at all by design, or
  - non_memory_tool_called and l2_store_confirmed are both true.

2. Auto-store deterministic tool outputs in code path.
- In executor_tools handling, when a non-memory tool returns successfully, automatically synthesize and persist a fact to L2 (system-level write), instead of relying on model discretion to call store_intermediate_fact.

3. Pass execution artifacts directly to Finalizer state.
- Add a structured execution_artifacts list in graph state containing tool name, normalized args, and normalized outputs.
- Finalizer should build evidence table from execution_artifacts first, then augment with YAAM L2 and L3.
- This guarantees evidence availability even if L2 is temporarily unavailable.

4. Use unique thread ids per run invocation.
- Replace thread id task_id with a run-scoped id, for example task_id plus timestamp or uuid.
- Keep task_id in metadata/session attributes for grouping, but do not reuse the same checkpoint thread for repeated reruns.

5. Add regression tests.
- Test that FINAL_EXECUTION_DONE is rejected if a non-memory tool ran without subsequent successful store_intermediate_fact.
- Test that rerunning the same task starts with a fresh thread state.
- Test that a qualitative categorical tool output (for example Kraljic strategic) is accepted into evidence construction.

## Conclusion
The failure was not caused by missing tool capability. The Kraljic tool returned a valid strategic categorization in trace segment 0. The failure occurred because storage and evidence propagation were left to model compliance instead of being enforced by graph logic.
