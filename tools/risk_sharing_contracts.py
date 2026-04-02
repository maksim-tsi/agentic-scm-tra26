import numpy as np
from scipy.optimize import minimize
from pydantic import BaseModel, ConfigDict
from typing import Dict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    demand_volatility: float = 0.0
    capacity_flexibility_requirement: float = 1.0
    production_stability_benefit: float = 1.0
    risk_sharing_contract_parameters: Dict[str, float] = {
        'lower_bound': 0.0,
        'upper_bound': 1.0,
        'initial_guess': 0.5
    }

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    optimal_contract_parameter: float = 0.0
    buyer_utility: float = 0.0
    supplier_utility: float = 0.0
    joint_profit: float = 0.0

def optimize_risk_sharing_contract(input_data: Input) -> Output:
    """
    WHEN TO USE THIS SKILL:
    This skill is used in outsourcing relationships where the buyer faces volatile demand and requires capacity flexibility to handle uncertainty, while the supplier benefits from stable production runs for economies of scale. It helps in determining optimal risk-sharing contract parameters to align incentives, balance the trade-off between flexibility and stability, and maximize global supply chain profit. Ideal for capacity planning decisions involving contract design in supply chain management, especially when addressing the strategic tension between buyer flexibility needs and supplier production stability.

    Inputs:
    - demand_volatility: float, non-negative measure of demand uncertainty (e.g., standard deviation of demand).
    - capacity_flexibility_requirement: float, positive value representing the level of flexibility needed by the buyer (e.g., as a factor between 0 and 1, where higher means more flexibility).
    - production_stability_benefit: float, positive economic benefit the supplier gains from stable production (e.g., cost savings per unit).
    - risk_sharing_contract_parameters: dict, containing keys for optimization bounds and initial guess:
        - 'lower_bound': float, lower bound for the contract parameter (e.g., risk-sharing factor).
        - 'upper_bound': float, upper bound for the contract parameter.
        - 'initial_guess': float, initial value for optimization.

    Output:
    - Output model with fields:
        - optimal_contract_parameter: float, the optimized risk-sharing factor.
        - buyer_utility: float, estimated buyer's utility at optimum.
        - supplier_utility: float, estimated supplier's utility at optimum.
        - joint_profit: float, estimated total supply chain profit improvement.
    """
    # Input validation
    if input_data.demand_volatility < 0:
        raise ValueError("demand_volatility must be non-negative.")
    if input_data.capacity_flexibility_requirement <= 0:
        raise ValueError("capacity_flexibility_requirement must be positive.")
    if input_data.production_stability_benefit <= 0:
        raise ValueError("production_stability_benefit must be positive.")
    if not isinstance(input_data.risk_sharing_contract_parameters, dict):
        raise ValueError("risk_sharing_contract_parameters must be a dictionary.")
    required_keys = ['lower_bound', 'upper_bound', 'initial_guess']
    for key in required_keys:
        if key not in input_data.risk_sharing_contract_parameters:
            raise ValueError(f"risk_sharing_contract_parameters must contain key '{key}'.")
    lower_bound = input_data.risk_sharing_contract_parameters['lower_bound']
    upper_bound = input_data.risk_sharing_contract_parameters['upper_bound']
    initial_guess = input_data.risk_sharing_contract_parameters['initial_guess']
    if lower_bound >= upper_bound:
        raise ValueError("lower_bound must be less than upper_bound.")
    if not (lower_bound <= initial_guess <= upper_bound):
        raise ValueError("initial_guess must be between lower_bound and upper_bound.")

    # Define utility functions based on a simple linear model
    # Buyer's utility: decreases with demand volatility, increases with flexibility and contract benefit
    # Supplier's utility: increases with stability benefit, decreases with contract cost
    # Contract parameter gamma represents risk-sharing factor (e.g., fraction of cost shared)
    def buyer_utility(gamma):
        # Higher gamma means more risk shared to supplier, benefiting buyer
        return -input_data.demand_volatility * (1 - input_data.capacity_flexibility_requirement) + gamma * input_data.production_stability_benefit

    def supplier_utility(gamma):
        # Lower gamma means less risk for supplier
        return input_data.production_stability_benefit * (1 - gamma) - input_data.demand_volatility * 0.1  # small penalty for volatility

    # Objective function to minimize negative joint utility (maximize joint profit)
    def objective(gamma):
        joint = buyer_utility(gamma) + supplier_utility(gamma)
        return -joint  # since minimize

    # Set bounds for optimization
    bounds = [(lower_bound, upper_bound)]
    result = minimize(objective, x0=[initial_guess], bounds=bounds, method='L-BFGS-B')

    if not result.success:
        raise ValueError("Optimization failed: " + result.message)

    optimal_gamma = result.x[0]
    buyer_util = buyer_utility(optimal_gamma)
    supplier_util = supplier_utility(optimal_gamma)
    joint_profit = buyer_util + supplier_util

    return Output(
        optimal_contract_parameter=float(optimal_gamma),
        buyer_utility=float(buyer_util),
        supplier_utility=float(supplier_util),
        joint_profit=float(joint_profit)
    )
