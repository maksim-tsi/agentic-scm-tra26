#!/bin/bash
# Phase 1: 50-task batch run for all validated baseline models

set -u

MODELS=(
  "x-ai/grok-4.1-fast"
  "meta-llama/llama-3.1-8b-instruct"
  "deepseek/deepseek-v3.2"
  "google/gemini-2.5-flash-lite"
  "openai/gpt-oss-120b"
  "openai/gpt-oss-20b"
)

LIMIT=50
RUN_MODE="AgenticGraph"

for MODEL in "${MODELS[@]}"; do
  echo "====================================================="
  echo "Starting Phase 1 Batch for Model: $MODEL"
  echo "====================================================="

  PYTHONPATH=src:. uv run python scripts/batch_resume_runner.py \
    --limit "$LIMIT" \
    --run-mode "$RUN_MODE" \
    --model-id "$MODEL"
done

echo "All Phase 1 batches completed!"
