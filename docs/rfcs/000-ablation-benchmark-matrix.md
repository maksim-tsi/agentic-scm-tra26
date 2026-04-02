# RFC 000 — Ablation Benchmark Matrix (v0)

## Status
Draft (v0; 2026-04-02)

## Motivation
We want to measure the effect of:
- Tool access vs no tool access
- Evidence Table emission vs no Evidence Table

## Methodological rationale for Naive+Evidence (L1/L2 memory)
The benchmark prompts intentionally resemble real “messy ops” communication: long context, distractors, inconsistent formatting, and partially redundant facts. This introduces **cognitive noise**.

We model this noise as a two-layer process:

- **L1 (Raw Context)**: the original prompt text (noisy, unstructured).
- **L2 (Working Knowledge)**: a normalized, structured representation extracted from L1 (the Evidence Table).

### Why force an Evidence Table?
**Naive+Evidence** requires the model to explicitly extract and normalize facts into L2 *before* doing any calculations. This makes it possible to separate two failure modes that are otherwise conflated:

- **Retrieval failure**: the model fails to extract the right facts from L1 into L2 (missing/incorrect values, wrong units, wrong interpretation).
- **Reasoning failure**: the model’s L2 facts are correct, but it still produces incorrect math/logic (calculation errors, formula misuse, invalid inference).

### Retrieval–Reasoning Gap (intended measurable claim)
Comparing **Naive** vs **Naive+Evidence** (same “no tools” constraint) isolates how much error comes from **fact extraction under noisy text** versus **core reasoning/calculation quality**.

If Naive+Evidence reduces error rates primarily by improving L2 quality (with no tool access), we can empirically demonstrate a **Retrieval–Reasoning Gap**: a measurable gap between being able to *retrieve/normalize* the right inputs and being able to *reason* with them.

## Evidence Table (lightweight template; not enforced)
In Naive+Evidence modes, the model SHOULD emit an Evidence Table prior to computations. This is a soft guideline (formatting is not a hard failure).

| Fact | Source snippet | Normalized value | Units | Role/use in solution |
|---|---|---:|---|---|
| (example) annual demand | “Demand is 12,000 units/year” | 12000 | units/year | input to EOQ cost calculation |

## Proposed modes (v0)
1) **Naive**: no tool calls; normal answer.
2) **Naive+Evidence**: no tool calls; requires evidence-style structured intermediate artifacts.
3) **Tools**: tool calls allowed; no Evidence Table required.
4) **Tools+Evidence**: tool calls allowed; Evidence Table required.

## Non-goals (for v0 placeholder)
- No strict schema enforcement that drops runs for small-model formatting failures.
- No evaluator changes mandated by this RFC; this document describes intended measurement modes.
