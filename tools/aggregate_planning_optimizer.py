import numpy as np
from scipy.optimize import linprog
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional, Dict


class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    periods: int = 3
    regular_labor_cost_per_worker_per_period: float = 1000.0
    overtime_cost_per_hour: float = 25.0
    hiring_cost_per_worker: float = 500.0
    layoff_cost_per_worker: float = 750.0
    holding_cost_per_unit: float = 2.0
    stockout_cost_per_unit: float = 5.0
    material_cost_per_unit: float = 10.0
    subcontract_cost_per_unit: float = 15.0
    demand: List[float] = [100.0, 150.0, 120.0]
    initial_inventory: float = 0.0
    initial_backorders: float = 0.0
    initial_workers: float = 10.0
    production_rate_per_worker: float = 10.0
    overtime_rate_per_hour: float = 2.0

    @field_validator('periods')
    @classmethod
    def periods_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('periods must be a positive integer')
        return v

    @field_validator('regular_labor_cost_per_worker_per_period',
                     'overtime_cost_per_hour',
                     'hiring_cost_per_worker',
                     'layoff_cost_per_worker',
                     'holding_cost_per_unit',
                     'stockout_cost_per_unit',
                     'material_cost_per_unit',
                     'subcontract_cost_per_unit')
    @classmethod
    def cost_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError('Cost values must be non-negative')
        return v

    @field_validator('demand')
    @classmethod
    def demand_must_match_periods(cls, v: List[float], info) -> List[float]:
        if 'periods' in info.data and len(v) != info.data['periods']:
            raise ValueError(f'Length of demand must equal periods ({info.data["periods"]})')
        if any(d < 0 for d in v):
            raise ValueError('Demand values must be non-negative')
        return v

    @field_validator('initial_inventory', 'initial_backorders', 'initial_workers')
    @classmethod
    def initial_values_must_be_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError('Initial values must be non-negative')
        return v

    @field_validator('production_rate_per_worker', 'overtime_rate_per_hour')
    @classmethod
    def rate_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Rate values must be positive')
        return v


class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    success: bool = False
    total_cost: Optional[float] = None
    decision_variables: Optional[Dict[str, List[float]]] = None
    message: str = ""


def solve_aggregate_planning(input_data: Input) -> Output:
    """
    WHEN TO USE THIS SKILL:
    This skill is designed for multi-period operational cost minimization in production planning contexts, such as aggregate planning in supply chain management. It solves for optimal workforce levels, overtime, hiring, layoffs, inventory, stockouts, production, and subcontracting over a planning horizon to minimize total costs including labor, hiring, holding, stockout, material, and subcontracting costs. Use this skill when you need to make trade-offs between these cost elements across multiple periods under deterministic demand patterns.

    Inputs:
    - periods (int): Number of periods in the planning horizon.
    - regular_labor_cost_per_worker_per_period (float): Cost per worker per period for regular labor.
    - overtime_cost_per_hour (float): Cost per overtime hour.
    - hiring_cost_per_worker (float): Cost per worker hired.
    - layoff_cost_per_worker (float): Cost per worker laid off.
    - holding_cost_per_unit (float): Holding cost per unit per period.
    - stockout_cost_per_unit (float): Stockout or backorder cost per unit.
    - material_cost_per_unit (float): Material cost per unit produced.
    - subcontract_cost_per_unit (float): Subcontracting cost per unit.
    - demand (list of float): Demand for each period, length must equal periods.
    - initial_inventory (float, optional): Initial inventory at period 0, default 0.0.
    - initial_backorders (float, optional): Initial backorders at period 0, default 0.0.
    - initial_workers (float, optional): Initial number of workers at period 0, default 0.0.
    - production_rate_per_worker (float, optional): Units produced per worker per period, default 1.0.
    - overtime_rate_per_hour (float, optional): Units produced per overtime hour, default 1.0.

    Output:
    - Output: A Pydantic model containing:
        - success (bool): Whether the optimization was successful.
        - total_cost (float or None): Minimum total operational cost.
        - decision_variables (dict or None): Optimal values for each variable over periods, with keys 'workers', 'overtime', 'hiring', 'layoff', 'inventory', 'stockout', 'production', 'subcontract'.
        - message (str): Status message from the solver.
    """
    # Defensive input validation beyond Pydantic
    if input_data.periods <= 0:
        raise ValueError("periods must be positive")
    if len(input_data.demand) != input_data.periods:
        raise ValueError(f"demand length {len(input_data.demand)} does not match periods {input_data.periods}")
    if any(d < 0 for d in input_data.demand):
        raise ValueError("demand contains negative values")
    
    periods = input_data.periods
    regular_labor_cost_per_worker_per_period = input_data.regular_labor_cost_per_worker_per_period
    overtime_cost_per_hour = input_data.overtime_cost_per_hour
    hiring_cost_per_worker = input_data.hiring_cost_per_worker
    layoff_cost_per_worker = input_data.layoff_cost_per_worker
    holding_cost_per_unit = input_data.holding_cost_per_unit
    stockout_cost_per_unit = input_data.stockout_cost_per_unit
    material_cost_per_unit = input_data.material_cost_per_unit
    subcontract_cost_per_unit = input_data.subcontract_cost_per_unit
    demand = input_data.demand
    initial_inventory = input_data.initial_inventory
    initial_backorders = input_data.initial_backorders
    initial_workers = input_data.initial_workers
    production_rate_per_worker = input_data.production_rate_per_worker
    overtime_rate_per_hour = input_data.overtime_rate_per_hour

    # Number of variables per period: 8 (W, O, H, L, I, S, P, C)
    n_vars_per_period = 8
    n_vars = n_vars_per_period * periods

    # Objective function coefficients (minimize cost)
    c = np.zeros(n_vars)
    for t in range(periods):
        base_idx = n_vars_per_period * t
        c[base_idx] = regular_labor_cost_per_worker_per_period      # W_t
        c[base_idx + 1] = overtime_cost_per_hour                    # O_t
        c[base_idx + 2] = hiring_cost_per_worker                    # H_t
        c[base_idx + 3] = layoff_cost_per_worker                    # L_t
        c[base_idx + 4] = holding_cost_per_unit                     # I_t
        c[base_idx + 5] = stockout_cost_per_unit                    # S_t
        c[base_idx + 6] = material_cost_per_unit                    # P_t
        c[base_idx + 7] = subcontract_cost_per_unit                 # C_t

    # Equality constraints: inventory balance and workforce balance
    n_eq_constraints = 2 * periods
    A_eq = np.zeros((n_eq_constraints, n_vars))
    b_eq = np.zeros(n_eq_constraints)

    for t in range(1, periods + 1):  # t from 1 to periods
        base_idx_curr = n_vars_per_period * (t - 1)
        
        # Inventory balance constraint for period t
        inv_row_idx = 2 * (t - 1)
        A_eq[inv_row_idx, base_idx_curr + 4] = 1  # I_t
        A_eq[inv_row_idx, base_idx_curr + 5] = -1  # -S_t (stockout reduces inventory)
        A_eq[inv_row_idx, base_idx_curr + 6] = -1  # -P_t (production uses inventory? Wait - inventory balance should be: I_t = I_{t-1} - S_{t-1} + P_t + C_t - demand_t)
        A_eq[inv_row_idx, base_idx_curr + 7] = -1  # -C_t (subcontract adds to inventory)
        
        if t > 1:
            base_idx_prev = n_vars_per_period * (t - 2)
            A_eq[inv_row_idx, base_idx_prev + 4] = -1  # -I_{t-1}
            A_eq[inv_row_idx, base_idx_prev + 5] = 1   # +S_{t-1} (previous stockout reduces current inventory)
            b_eq[inv_row_idx] = - demand[t - 1]
        else:  # t == 1
            b_eq[inv_row_idx] = - demand[0] - (initial_inventory - initial_backorders)

        # Workforce balance constraint for period t
        wf_row_idx = 2 * (t - 1) + 1
        A_eq[wf_row_idx, base_idx_curr] = 1      # W_t
        A_eq[wf_row_idx, base_idx_curr + 2] = -1  # -H_t (hiring increases workforce)
        A_eq[wf_row_idx, base_idx_curr + 3] = 1   # +L_t (layoff decreases workforce)
        if t > 1:
            base_idx_prev = n_vars_per_period * (t - 2)
            A_eq[wf_row_idx, base_idx_prev] = -1  # -W_{t-1}
            b_eq[wf_row_idx] = 0
        else:  # t == 1
            b_eq[wf_row_idx] = initial_workers

    # Inequality constraints: production capacity (P_t <= production_rate_per_worker * W_t + overtime_rate_per_hour * O_t)
    n_ub_constraints = periods
    A_ub = np.zeros((n_ub_constraints, n_vars))
    b_ub = np.zeros(n_ub_constraints)

    for t in range(1, periods + 1):
        base_idx = n_vars_per_period * (t - 1)
        row_idx = t - 1
        A_ub[row_idx, base_idx + 6] = 1  # P_t
        A_ub[row_idx, base_idx] = -production_rate_per_worker  # -production_rate_per_worker * W_t
        A_ub[row_idx, base_idx + 1] = -overtime_rate_per_hour  # -overtime_rate_per_hour * O_t
        b_ub[row_idx] = 0

    # Bounds: all variables non-negative
    bounds = [(0, None) for _ in range(n_vars)]

    # Solve linear programming problem
    try:
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    except Exception as e:
        return Output(success=False, total_cost=None, decision_variables=None, message=f'Solver error: {e}')

    if result.success:
        # Extract decision variables
        decision_vars = {
            'workers': [],
            'overtime': [],
            'hiring': [],
            'layoff': [],
            'inventory': [],
            'stockout': [],
            'production': [],
            'subcontract': []
        }
        for t in range(periods):
            base_idx = n_vars_per_period * t
            decision_vars['workers'].append(result.x[base_idx])
            decision_vars['overtime'].append(result.x[base_idx + 1])
            decision_vars['hiring'].append(result.x[base_idx + 2])
            decision_vars['layoff'].append(result.x[base_idx + 3])
            decision_vars['inventory'].append(result.x[base_idx + 4])
            decision_vars['stockout'].append(result.x[base_idx + 5])
            decision_vars['production'].append(result.x[base_idx + 6])
            decision_vars['subcontract'].append(result.x[base_idx + 7])

        return Output(success=True, total_cost=float(result.fun), decision_variables=decision_vars, message='Optimization successful.')
    else:
        return Output(success=False, total_cost=None, decision_variables=None, message=result.message)