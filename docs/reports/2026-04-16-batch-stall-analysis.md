# Batch Stall Analysis (First 19 Attempted Tasks)

Generated at: 2026-04-17T06:41:09.531682+00:00
Checkpoint DB: `outputs/langgraph_checkpoints.sqlite`
Phoenix URL: `http://127.0.0.1:6006`
Phoenix project: `scm-cert-eval-sandbox`

## 1) Checkpoint Analysis (SQLite)

### Task-by-task step/checkpoint distribution

| Order | Task ID | Thread ID | Checkpoints | Step min | Step max | Unique steps | Signals |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | db_port_buffer_001 | db_port_buffer_001_d7b15f1c | 7 | -1 | 5 | 7 | none |
| 2 | newsvendor_covid_port_analysis | newsvendor_covid_port_analysis_679afac3 | 9 | -1 | 7 | 9 | none |
| 3 | port_zhuhai_redundant_system_2024 | port_zhuhai_redundant_system_2024_2c863293 | 7 | -1 | 5 | 7 | none |
| 4 | f47ac10b-58cc-4372-a567-0e02b2c3d479 | f47ac10b-58cc-4372-a567-0e02b2c3d479_552dd246 | 7 | -1 | 5 | 7 | none |
| 5 | SC-EDD-PSA-001 | SC-EDD-PSA-001_21208f4f | 13 | -1 | 11 | 13 | none |
| 6 | demand_forecast_001 | demand_forecast_001_649037c3 | 7 | -1 | 5 | 7 | none |
| 7 | sc_mrp_gross_req_001 | sc_mrp_gross_req_001_45150f6d | 5 | -1 | 3 | 5 | none |
| 8 | SC-WC-LOAD-001 | SC-WC-LOAD-001_f07ab58f | 7 | -1 | 5 | 7 | none |
| 9 | marine_dues_calculation_001 | marine_dues_calculation_001_2f23a5ba | 7 | -1 | 5 | 7 | none |
| 10 | inventory_order_qty_001 | inventory_order_qty_001_31bd4750 | 9 | -1 | 7 | 9 | none |
| 11 | sc_prod_seq_001 | sc_prod_seq_001_55bf273a | 4 | -1 | 2 | 4 | validation=1 |
| 12 | sc_safety_stock_001 | sc_safety_stock_001_a96b22b8 | 5 | -1 | 3 | 5 | none |
| 13 | SC-MPS-2024-001 | SC-MPS-2024-001_883cd2cd | 23 | -1 | 21 | 23 | rate_limit=2 |
| 14 | mrp_lead_time_offset_001 | mrp_lead_time_offset_001_e2800890 | 7 | -1 | 5 | 7 | none |
| 15 | dwell_time_hamburg_exponential_2025_01 | dwell_time_hamburg_exponential_2025_01_7b98549d | 5 | -1 | 3 | 5 | none |
| 16 | FMEA_RPN_Mawan_SmartPort_001 | FMEA_RPN_Mawan_SmartPort_001_8166e00b | 7 | -1 | 5 | 7 | none |
| 17 | sc_postponement_valencia_001 | sc_postponement_valencia_001_66628af4 | 7 | -1 | 5 | 7 | validation=1 |
| 18 | sc_quality_principles_mapping_001 | sc_quality_principles_mapping_001_3f8194be | 5 | -1 | 3 | 5 | none |
| 19 | sc_ra_001 | sc_ra_001_a983ebae | 8525 | -1 | 8523 | 8525 | rate_limit=19 |

### Distribution summary

- Tasks analyzed: 19
- Mean checkpoints per task: 456.11
- P95 checkpoints per task: 873.20
- Mean max-step per task: 454.11
- P95 max-step per task: 871.20
- Max-step trend slope (tasks 1->N): 134.451 per task
- Checkpoint-count trend slope (tasks 1->N): 134.451 per task

### Stall point diagnosis (latest attempted task)

- Final task ID: `sc_ra_001`
- Final thread ID: `sc_ra_001_a983ebae`
- Last checkpoint ID: `1f13a1e5-0f18-6c0d-a14b-f58a53650430`
- Last parent checkpoint ID: `1f13a1e5-0f0d-6ec0-a14a-45a63524d7ad`
- Source counts: `{"input": 1, "loop": 8524}`
- Channel counts: `{"branch:to:executor": 4262, "branch:to:executor_tools": 4261, "branch:to:planner": 1, "messages": 8524, "retrieved_context": 1, "task_data": 1}`
- Detected issue: **OpenRouter rate-limit surfaced in write payloads**
- Last checkpoint metadata preview: `{"source": "loop", "step": 8523, "parents": {}, "task_id": "sc_ra_001", "model_id": "x-ai/grok-4.1-fast"}`

## 2) Trace & Latency Analysis (Arize Phoenix)

- Phoenix query error: Phoenix query returned no spans for any fallback project/time window

## 3) Recommendations

- Add a hard LangGraph step cap (for example 25-30) with explicit fail-fast error annotation.
- Add per-node wall-clock timeouts around planner/executor/executor_tools transitions.
- Add retry budget caps for repetitive validation failures; escalate after N retries.
- Persist an explicit terminal status artifact per task (success, rate-limit, timeout, validation-loop).
- Add a batch watchdog: if no new successful task completion within a time window, stop and emit diagnostics.
