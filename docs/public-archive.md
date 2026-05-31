# Public Archive Notes

This repository is preserved as a public academic archive for the TRA 2026 SCM-MAS evaluation harness.

## What Is Included

- Questions-only benchmark inputs under `data/benchmark/`.
- Deterministic SCM tool implementations under `tools/`.
- Runnable evaluator/orchestrator code under `src/` and `scripts/`.
- Public architecture, evaluator contract, prompts, and RFC notes under `docs/`.
- Dependency manifests (`pyproject.toml`, `uv.lock`, and `requirements.txt` fallback).

## What Is Excluded From The Public Archive Tip

The following materials are intentionally local-only and ignored:

- Runtime outputs and traces under `outputs/`.
- Local `.env` files and provider credentials.
- Dated internal reports, development logs, and paper-analysis notes.
- Legacy v1 prototypes, notebooks, spreadsheets, and external workflow experiments.
- One-off local trace/debug scripts used during paper preparation.

These exclusions reduce accidental disclosure risk and keep the archive focused on the reproducible code and benchmark surface.

## Preservation Notes

The public archive tip removes local-only materials from version control, but local working copies can still retain those files for private preservation. If historical commits must also be scrubbed from a public host, use a deliberate history-rewrite or fresh archive repository process and coordinate branch/tag retention before force-pushing.
