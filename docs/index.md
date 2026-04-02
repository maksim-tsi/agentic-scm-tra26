# Docs index

This directory is the repository’s **system of record** for agent + evaluator behavior.
Start here when making changes.

## Read first
- `docs/architecture.md` — repo map and boundaries (what is read-only / versioned).
- `docs/evaluation/contract.md` — evaluation I/O contracts and scoring expectations.

## Prompts
- `docs/prompts/scm_agent_system_prompt.md` — benchmarked SCM agent “constitution” (soft format guidance).

## RFCs (design history)
- `docs/rfcs/000-ablation-benchmark-matrix.md` — placeholder for the upcoming evaluation ablation matrix.
- `docs/rfcs/001-native-tool-calling-evaluator.md` — tool calling evaluator design (strict Pydantic boundary; no code execution).
