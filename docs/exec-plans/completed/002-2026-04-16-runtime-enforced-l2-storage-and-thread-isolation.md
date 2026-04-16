# Execution Plan 002 — 2026-04-16 Runtime-Enforced L2 Storage And Thread Isolation

## Purpose
Implement two architectural fixes that remove model discretion from evidence persistence and eliminate state contamination across reruns:

1. Unique checkpoint thread per orchestrator invocation.
2. Automatic L2 storage on every successful deterministic SCM tool execution.

This plan intentionally prioritizes deterministic runtime enforcement over prompt compliance.

## Scope
In scope:
- scripts/run_orchestrator.py
- src/agentic/nodes/executor.py
- Validation run for task sc_ra_001

Out of scope for this change set:
- Finalizer schema redesign
- New evidence_table assembly logic from execution_artifacts
- Migration of existing checkpoint history

## Preconditions
- uv environment synced with lock file.
- Outputs directory writable.
- YAAM environment variables configured for L2 operations.
- OPENROUTER API credentials configured.

## Implementation Plan

### Step 1 — Unique thread per run invocation
File: scripts/run_orchestrator.py

Changes:
1. Import uuid.
2. In AgenticGraph path, generate a per-invocation thread id:
   - thread_id = f"{task.task_id}_{uuid.uuid4().hex[:8]}"
3. Use generated thread_id in graph.invoke config configurable block.
4. Keep task_data.task_id unchanged to preserve logical grouping for YAAM and reporting.

Rationale:
- Prevent cross-run message carryover in outputs/langgraph_checkpoints.sqlite.
- Keep persistent history isolated per execution while preserving task identity semantics.

Acceptance criteria:
- Two consecutive runs of the same task produce different thread ids.
- Latest checkpoint for each run contains only that run’s message flow.

### Step 2 — Remove LLM-controlled store tool
File: src/agentic/nodes/executor.py

Changes:
1. Delete store_intermediate_fact tool function.
2. Remove ToolRuntime and tool imports no longer needed.
3. Remove store_intermediate_fact from all_tools.
4. Update EXECUTOR_SYSTEM_PROMPT to remove storage instruction:
   - Keep only execution constraints and FINAL_EXECUTION_DONE condition.

Rationale:
- LLM should not be trusted to decide memory persistence steps.
- Reduces policy surface and instruction conflict risk.

Acceptance criteria:
- Executor still binds deterministic SCM tools successfully.
- No store_intermediate_fact tool appears in bound tool schemas.

### Step 3 — Add runtime auto-store in tool wrapper
File: src/agentic/nodes/executor.py

Design recommendation:
Use runtime context injection in wrapped tool function so task_id is available directly when tool executes.

Recommended wrapped signature:
- wrapped_tool(runtime: ToolRuntime, **kwargs)

Auto-store flow inside wrapped tool:
1. Validate input via input_model.model_validate.
2. Execute SCM tool.
3. Serialize successful result to stable text payload.
4. Resolve task_id from runtime.state.task_data.task_id first, then runtime.config.configurable.task_id fallback.
5. If task_id exists:
   - Initialize YaamSemanticClient.from_env
   - Call store_l2_fact with:
     - session_id = task_id
     - agent_id = tra-scm-executor
     - task_id = task_id
     - content = "Tool <tool_alias> returned: <serialized_result>"
     - traceparent best-effort (reuse existing helper)
6. Wrap YAAM write in try/except/finally so persistence issues never fail tool execution.
7. Return tool result payload to model exactly as today.

Error handling requirements:
- ValidationError returns existing Validation Error message string.
- Tool runtime errors return existing Tool Error message string.
- YAAM write errors should only append an internal warning path (loggable), not alter success output contract.

Rationale:
- Guarantees all successful tool outputs are persisted regardless of model behavior.
- Maintains walled-garden behavior and prevents evidence drop due to skipped tool call.

Acceptance criteria:
- After any successful SCM tool call, one L2 fact write attempt occurs.
- Tool output returned to model remains unchanged from current schema/format.
- YAAM outage does not crash executor tool loop.

### Step 4 — Validate end-to-end on sc_ra_001
Run command:
PYTHONPATH=src:. uv run python scripts/run_orchestrator.py --run-mode AgenticGraph --task-id sc_ra_001

Validation checks:
1. Orchestrator exits successfully.
2. execution_metrics.tools_called includes kraljic_matrix__kraljic_supply_matrix_classification.
3. Checkpoint thread for this run is unique (task_id suffix present).
4. Trace inspection confirms L2 write attempt occurred after successful tool output.
5. Final response should no longer claim total absence of facts if tool executed successfully.

## Recommended Verification Strategy

### A. Fast static checks
- Run focused tests for graph router and executor tool flow.
- Run import smoke tests.

### B. Runtime diagnostics
- Re-run scripts/debug_trace_sc_ra_001.py after implementation.
- Confirm:
  - latest_segment_has_tool_calls true when SCM tool used
  - no dependence on store_intermediate_fact tool call path
  - thread segmentation no longer mixes runs in a single thread id

### C. Regression guardrails to add next
1. Test that repeated same task runs produce distinct thread ids.
2. Test that successful SCM tool execution triggers exactly one YAAM store attempt.
3. Test that YAAM failure path does not break tool return contract.

## Risks And Mitigations

Risk 1: ToolRuntime injection with StructuredTool may not pass runtime as expected.
Mitigation:
- Implement minimal proof run with a single tool call.
- If runtime injection is unavailable, fallback to ToolNode post-processing hook to persist successful ToolMessage outputs.

Risk 2: Excessive L2 writes on high tool-call tasks.
Mitigation:
- Keep content concise and deterministic.
- Add optional dedup/hash policy in follow-up if volume becomes an issue.

Risk 3: YAAM latency affects tool throughput.
Mitigation:
- Maintain best-effort non-fatal writes.
- Consider async queueing in future, but not required for this fix.

Risk 4: Historical thread data remains mixed from past runs.
Mitigation:
- Treat prior data as legacy.
- Validate only new runs after unique-thread rollout.

## Rollout Recommendation
1. Implement Step 1 and Step 2 in one patch.
2. Implement Step 3 with minimal behavior delta to existing tool wrapper output.
3. Execute Step 4 command on sc_ra_001.
4. Re-run diagnostic script and confirm evidence persistence path.
5. If clean, proceed to broader benchmark smoke run.

## Definition Of Done
- Unique per-run thread id is active in AgenticGraph invocations.
- store_intermediate_fact tool is removed.
- Successful deterministic tool executions trigger runtime-managed L2 write attempts.
- sc_ra_001 run completes and trace evidence confirms persistence path execution.
