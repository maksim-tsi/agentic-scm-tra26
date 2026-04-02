# Evaluators — Agent Instructions

## Purpose
`src/evaluators/` defines evaluation targets (naive vs agentic) and the evaluator contract.

## Rules
- Preserve raw outputs; do not drop runs solely due to formatting violations.
- Treat output-format guidance (`<FINAL_ANSWER>`) as a metric, not a hard constraint.
- Write artifacts to `outputs/` (gitignored).

