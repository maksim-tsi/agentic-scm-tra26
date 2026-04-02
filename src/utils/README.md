# Utilities

This directory contains helper utilities for:

- Metric computation (e.g., Accuracy, Fidelity Score)
- Trace ingestion and post-processing (e.g., Arize Phoenix exports)

Implementation is intentionally deferred until benchmark/task schemas are finalized.

## Expected Inputs

- Benchmark task payloads from `data/benchmark/`.
- Evaluator outputs (`EvalResult`) from `src/evaluators/`.
- Optional trace artifacts from agentic execution runs.

## Planned Utility Areas

- Accuracy computation against benchmark expectations or rubric outputs.
- Fidelity/scoring utilities for structured response quality checks.
- Trace normalization/export helpers for observability tooling.

## Status Note

These utilities are placeholders today and should be implemented only after evaluator response contracts and scoring schemas are finalized.

