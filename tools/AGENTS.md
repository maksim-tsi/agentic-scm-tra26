# Tools — Agent Instructions

## Purpose
`tools/` contains deterministic SCM skills used by the agentic path.

## Rules
- Treat tool implementations as **benchmarked** and effectively read-only.
- Avoid behavior changes unless you introduce an explicit, versioned update path.
- Keep tools deterministic: no filesystem or network side effects.
- Inputs/outputs must remain Pydantic v2 models with strict validation.

## Registry
- Active exports live in `tools/__init__.py` via `ACTIVE_TOOLS`.
- Update the registry only via `scripts/bootstrap_active_tools.py` (manifest-driven).

