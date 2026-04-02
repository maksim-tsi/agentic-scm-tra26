# RFC 000 — Ablation Benchmark Matrix (Placeholder)

## Status
Placeholder (to be finalized after initial Harness Engineering scaffolding lands).

## Motivation
We want to measure the effect of:
- Tool access vs no tool access
- Evidence Table emission vs no Evidence Table

## Proposed modes (v0)
1) **Naive**: no tool calls; normal answer.
2) **Naive+Evidence**: no tool calls; requires evidence-style structured intermediate artifacts.
3) **Tools**: tool calls allowed; no Evidence Table required.
4) **Tools+Evidence**: tool calls allowed; Evidence Table required.

## Non-goals (for v0 placeholder)
- No strict schema enforcement that drops runs for small-model formatting failures.
- No evaluator changes in this RFC stub; only documents intended direction.

