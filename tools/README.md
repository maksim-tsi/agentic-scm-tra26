# Tools (Skill Factory)

This directory hosts deterministic Python skills imported from the Skill Factory.

## Runtime Export Contract

- Active runtime exports are defined in `tools/__init__.py` through `ACTIVE_TOOLS`.
- Each exported callable is aliased with the pattern `module__function`.
- `__all__` mirrors the active export surface for explicit imports.

## Tool Categories

Inventory and Replenishment:

- `abc_classification.py`
- `economic_order_quantity.py`
- `inventory_turnover.py`
- `newsvendor_model.py`
- `reorder_point_safety_stock.py`
- `risk_pooling.py`

Planning, Scheduling, and MRP:

- `aggregate_planning_optimizer.py`
- `edd_dispatching.py`
- `mps_projected_available_balance.py`
- `mrp_net_requirements.py`
- `mrp_pegging.py`
- `toc_bottleneck_analysis.py`
- `work_center_load.py`

Forecasting and Demand Analysis:

- `bullwhip_effect.py`
- `linear_trend_forecast.py`
- `moving_average.py`
- `seasonal_decomposition.py`

Quality, Risk, and Process Control:

- `apics_rule_check.py`
- `fmea_rpn.py`
- `p_chart_ucl.py`
- `pert_cpm_variance.py`
- `process_capability_cpk.py`
- `xbar_s_control_charts.py`

Logistics and Network Optimization:

- `centroid_location.py`
- `facility_location_optimizer.py`
- `ocean_freight_costing.py`
- `terminal_throughput.py`
- `transport_route_savings.py`

Strategic and Financial Analysis:

- `kraljic_matrix.py`
- `make_or_buy.py`
- `pareto_analysis.py`
- `pestel_analysis.py`
- `pricing_optimization.py`
- `return_on_assets.py`
- `risk_sharing_contracts.py`

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

