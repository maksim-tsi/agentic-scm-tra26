# agentic-scm-tra26 — Agent Instructions (Repo Map)

This `AGENTS.md` is intentionally short. Treat it as a **map**, not a manual.
Canonical documentation lives under `docs/` (start at `docs/index.md`).

## What this repo is
- Evaluation harness for comparing **naive LLM baselines** vs an **agentic SCM MAS** with deterministic SCM tools.
- Key directories:
  - `docs/` — system-of-record knowledge base (contracts, prompts, RFCs).
  - `data/benchmark/` — golden benchmark inputs (JSONL).
  - `tools/` — deterministic SCM skills (typed Pydantic I/O).
  - `src/evaluators/` — evaluator scaffolding (naive + agentic clients).
  - `tests/` — mechanical invariants + smoke tests.
  - `outputs/` — runtime artifacts (gitignored except `outputs/README.md`).

## Hard rules (do not violate)
- **No secrets**: never commit `.env`, API keys, tokens, or credentials.
- **Write outputs only to `outputs/`** (or other gitignored paths). Never write into `data/benchmark/`.
- **Treat `data/benchmark/` as immutable** for reproducibility. If it must change, create a versioned dataset artifact.
- **Treat `tools/` as benchmarked**. Avoid behavioral edits; if changes are required, use a versioned update path.

## Golden commands (local)
Preferred workflow uses `uv` + `uv.lock` for reproducibility.

- Setup env: `./scripts/setup.sh`
- Run tests: `./scripts/test.sh`
- Validate tool registry (no write): `uv run python scripts/bootstrap_active_tools.py --check`
- Regenerate tool registry (writes): `uv run python scripts/bootstrap_active_tools.py --write`

## Where to look first
- Repo TOC: `docs/index.md`
- Architecture + read-only boundaries: `docs/architecture.md`
- Evaluator contracts and what is scored: `docs/evaluation/contract.md`
- Benchmarked SCM agent system prompt (constitution): `docs/prompts/scm_agent_system_prompt.md`
- Upcoming benchmark ablations (placeholder RFC): `docs/rfcs/000-ablation-benchmark-matrix.md`

## If you get stuck
- Confirm env + deps: `uv sync --dev --frozen`
- Run fast checks: `uv run pytest -q`
- Inspect active tools: `uv run python -c "import tools; print(len(tools.ACTIVE_TOOLS))"`
- Search codebase: `rg -n "TODO|NotImplementedError" src tools docs`

