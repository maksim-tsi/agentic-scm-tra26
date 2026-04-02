# Tools (Skill Factory)

This directory hosts deterministic Python skills imported from the Skill Factory.

## Runtime Export Contract

- Active runtime exports are defined in `tools/__init__.py` through `ACTIVE_TOOLS`.
- Each exported callable is aliased with the pattern `module__function`.
- `__all__` mirrors the active export surface for explicit imports.
- Current active export count: 35 tool functions from 35 modules.

## Tool Categories

Inventory and Replenishment:

- [abc_classification.py](abc_classification.py): classify items by annual consumption value into A/B/C groups (`abc_classification__abc_inventory_categorization`).
- [economic_order_quantity.py](economic_order_quantity.py): compute annual ordering plus carrying cost for EOQ analysis (`economic_order_quantity__calculate_total_annual_inventory_cost`).
- [inventory_turnover.py](inventory_turnover.py): compute inventory turnover efficiency (`inventory_turnover__calculate_inventory_turnover`).
- [newsvendor_model.py](newsvendor_model.py): evaluate single-period stochastic order decision (`newsvendor_model__evaluate_newsvendor_strategy`).
- [reorder_point_safety_stock.py](reorder_point_safety_stock.py): compute safety stock and reorder point under uncertainty (`reorder_point_safety_stock__calculate_reorder_point_safety_stock`).
- [risk_pooling.py](risk_pooling.py): estimate safety-stock reduction from demand aggregation (`risk_pooling__demand_aggregation_safety_stock_reduction`).

Planning, Scheduling, and MRP:

- [aggregate_planning_optimizer.py](aggregate_planning_optimizer.py): optimize aggregate production plan with capacity/cost constraints (`aggregate_planning_optimizer__solve_aggregate_planning`).
- [edd_dispatching.py](edd_dispatching.py): select next job using earliest due date priority (`edd_dispatching__select_edd_job`).
- [mps_projected_available_balance.py](mps_projected_available_balance.py): compute projected available balance by period in MPS (`mps_projected_available_balance__compute_projected_available_balance`).
- [mrp_net_requirements.py](mrp_net_requirements.py): compute MRP net requirements from gross demand and inventory (`mrp_net_requirements__calculate_net_requirements`).
- [mrp_pegging.py](mrp_pegging.py): trace component requirements back to parent demand sources (`mrp_pegging__mrp_pegging_tracing`).
- [toc_bottleneck_analysis.py](toc_bottleneck_analysis.py): analyze TOC bottleneck, throughput, and scheduling recommendations (`toc_bottleneck_analysis__analyze_toc_scheduling`).
- [work_center_load.py](work_center_load.py): compute total work-center load from planned releases (`work_center_load__calculate_work_center_load`).

Forecasting and Demand Analysis:

- [bullwhip_effect.py](bullwhip_effect.py): identify demand amplification across supply chain echelons (`bullwhip_effect__bullwhip_effect_identifier`).
- [linear_trend_forecast.py](linear_trend_forecast.py): forecast demand using least-squares linear trend (`linear_trend_forecast__linear_trend_forecast`).
- [moving_average.py](moving_average.py): forecast demand using simple moving average (`moving_average__moving_average_forecast`).
- [seasonal_decomposition.py](seasonal_decomposition.py): compute seasonal indices and deseasonalized series (`seasonal_decomposition__calculate_seasonal_indices`).

Quality, Risk, and Process Control:

- [apics_rule_check.py](apics_rule_check.py): validate SCM reasoning against APICS definitions (`apics_rule_check__validate_scm_reasoning`).
- [fmea_rpn.py](fmea_rpn.py): compute risk priority number for FMEA failure modes (`fmea_rpn__calculate_rpn`).
- [p_chart_ucl.py](p_chart_ucl.py): compute upper control limit for p-charts (`p_chart_ucl__calculate_ucl_p_chart`).
- [pert_cpm_variance.py](pert_cpm_variance.py): aggregate variance across critical-path activities (`pert_cpm_variance__aggregate_critical_path_variance`).
- [process_capability_cpk.py](process_capability_cpk.py): compute Cpu/Cpl/Cpk process capability metrics (`process_capability_cpk__calculate_process_capability_indices`).
- [xbar_s_control_charts.py](xbar_s_control_charts.py): compute control limits for xbar-s charts (`xbar_s_control_charts__calculate_control_limits`).

Logistics and Network Optimization:

- [centroid_location.py](centroid_location.py): compute weighted centroid for location planning (`centroid_location__main`).
- [facility_location_optimizer.py](facility_location_optimizer.py): optimize facility selection and capacity allocation (`facility_location_optimizer__optimize_facility_location`).
- [ocean_freight_costing.py](ocean_freight_costing.py): compute total all-in ocean freight cost (`ocean_freight_costing__calculate_total_freight_cost`).
- [terminal_throughput.py](terminal_throughput.py): estimate container terminal truck-side service capacity (`terminal_throughput__calculate_terminal_truck_capacity`).
- [transport_route_savings.py](transport_route_savings.py): compute cost savings from route synchronization/rotation (`transport_route_savings__calculate_direct_rotation_cost_savings`).

Strategic and Financial Analysis:

- [kraljic_matrix.py](kraljic_matrix.py): classify items in the Kraljic supply matrix (`kraljic_matrix__kraljic_supply_matrix_classification`).
- [make_or_buy.py](make_or_buy.py): recommend make-vs-buy decision for modular components (`make_or_buy__make_buy_decision`).
- [pareto_analysis.py](pareto_analysis.py): apply 80/20 prioritization to drivers or defects (`pareto_analysis__apply_pareto_principle`).
- [pestel_analysis.py](pestel_analysis.py): run macro-environmental PESTEL assessment (`pestel_analysis__perform_pestel_analysis`).
- [pricing_optimization.py](pricing_optimization.py): compute optimal retail price under economic assumptions (`pricing_optimization__optimal_retail_pricing`).
- [return_on_assets.py](return_on_assets.py): compute return on assets metric (`return_on_assets__calculate_return_on_total_assets`).
- [risk_sharing_contracts.py](risk_sharing_contracts.py): optimize risk-sharing contract structures (`risk_sharing_contracts__optimize_risk_sharing_contract`).

## Registry Directory

- `tools/registry/` is reserved for dynamic discovery/registration helpers.
- The repository currently uses static registration in `tools/__init__.py`.
- `tools/registry/__init__.py` is intentionally empty at this stage.

## Conventions

- Skills should be importable Python modules.
- Inputs and outputs are defined with Pydantic models.
- Validation failures should raise clear `ValueError` messages.

## Read-Only Policy

In this benchmark workflow, imported tool implementations are treated as read-only.
If you need behavioral changes, create a versioned update path rather than silently modifying existing benchmarked tool behavior.

