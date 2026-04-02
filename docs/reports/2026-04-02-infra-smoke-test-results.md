# Infra Smoke Test Results Report

Date: 2026-04-02
Owner: Copilot implementation session
Scope: OpenRouter connectivity, Arize Phoenix trace ingestion and retrieval validation, smoke-test robustness fixes

## Executive Summary

Infrastructure smoke validation was executed end-to-end from this repository on macOS using uv and the project virtual environment.

Final status:
- OpenRouter connectivity: Pass
- Phoenix collector ingestion: Pass
- Phoenix API retrieval and trace-content verification: Pass
- Default smoke model set execution: Pass

## Repository Context

- Smoke script under test: scripts/smoke_test_infra.py
- Env template used: .env.example with local .env values
- Canonical execution plan reference: docs/exec-plans/001-infra-smoke-test.md

## What Was Implemented

Two reliability fixes were implemented in the smoke script after observing false-negative failures:

1. Phoenix span payload compatibility
- Problem: Phoenix span responses were list-of-dict payloads, while the validation path expected object attributes.
- Change: Added dict-safe span handling for attributes, trace id, span name, and output scanning.
- Outcome: Trace parent-child matching became reliable and canary validation passed.

2. Completion truncation mitigation
- Problem: Some models intermittently returned truncated or empty content under strict short token budgets.
- Change: Increased default completion budget and made it configurable through SMOKE_TEST_MAX_TOKENS.
- Outcome: Model output validation stabilized and full default run passed.

## Commands Executed

1. Dependency sync
- uv sync --dev --frozen

2. Canary smoke run
- PYTHONPATH=src:tools uv run python scripts/smoke_test_infra.py --model x-ai/grok-4.1-fast --timeout-s 90

3. Full smoke run
- PYTHONPATH=src:tools uv run python scripts/smoke_test_infra.py --timeout-s 120

4. Independent Phoenix endpoint verification
- Python snippet executed against Phoenix client API to confirm:
  - parent span name scm.infra_smoke_test
  - matching scm.eval.task_id, scm.eval.model_id, scm.eval.run_mode
  - child output containing SCM-INFRA-OK

## Final Smoke Run Results

Default model set:
- x-ai/grok-4.1-fast: PASS
- meta-llama/llama-3.1-8b-instruct: PASS
- deepseek/deepseek-v3.2: PASS
- google/gemini-2.5-flash-lite: PASS
- openai/gpt-oss-120b: PASS
- openai/gpt-oss-20b: PASS

## Independent Phoenix Trace Retrieval Results

Phoenix endpoint queried directly for the same execution window.

Observed:
- Project: scm-cert-eval-sandbox
- Total spans in query window: 56
- Each default model had at least one matching parent span with scm.eval attributes.
- Each model had at least one child span payload containing SCM-INFRA-OK.

Conclusion:
- Trace retrieval is working from the Phoenix API endpoint.
- App-level smoke path is functioning end-to-end under current configuration.

## Files Changed During Implementation

- scripts/smoke_test_infra.py

Key updates in file:
- Added dict-safe parsing in span helper logic.
- Added configurable token budget with default constant and env override.

## Known Notes

- The Phoenix tracing bootstrap currently logs a warning recommending BatchSpanProcessor for production.
- Current script behavior remains valid for smoke and validation use cases.

## Repro Checklist

1. Ensure .env contains OPENROUTER_API_KEY and Phoenix endpoint inputs.
2. Run uv sync --dev --frozen.
3. Run smoke command with PYTHONPATH=src:tools.
4. Confirm all PASS lines.
5. Confirm Phoenix API traces by project/task/model and expected output text.
