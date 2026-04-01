# SCM-MAS Evaluation Framework (TRA 2026)

Evaluation harness for comparing **zero-shot “naive” LLMs** (via OpenRouter) against our **agentic MAS** that combines **YAAM memory** and **Skill Factory tools**, with support for **DTR**-style execution/tracing.

## Architecture Theory

- **YAAM (Yet-Another Agent Memory):** persistent memory layer used by the Agentic MAS during task execution.
- **Skill Factory:** curated tool library (Python skills) used by the Agentic MAS to ground actions in deterministic capabilities.

## Evaluation Targets

1. **Zero-shot Naive LLMs** (e.g., Gemma, Llama 3, Mistral via OpenRouter).
2. **Agentic MAS** (YAAM-based + DTR + SCM Skills).

## Benchmarks

- **SCM-Cert-Bench (119 verified tasks):** TODO (add public link).

## Repository Layout

- `tools/` — Python skills imported from Skill Factory.
- `data/benchmark/` — golden benchmark tasks (JSON/JSONL) + metadata.
- `src/evaluators/` — evaluation clients and runner logic (naive vs agentic).
- `src/utils/` — metric computation (Accuracy, Fidelity Score) and trace processing (Arize Phoenix).
- `outputs/` — runtime logs, JSON reports, and YAAM memory dumps (not committed).

## Setup

### Requirements

- Python **3.10+**

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables

- `OPENROUTER_API_KEY` (required for naive LLM target)
- `PYTHONPATH=src:tools` (recommended for local imports)

Optional (depending on what you run):

- `OPENROUTER_MODEL`
- `OPENROUTER_BASE_URL`
- `YAAM_AGENT_URL`
- `YAAM_AGENT_API_KEY`

Create a local `.env` from the template:

```bash
cp .env.example .env
```

