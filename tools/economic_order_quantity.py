from typing import Optional
from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    annual_demand: Optional[float] = None
    order_quantity: Optional[float] = None
    order_cost: Optional[float] = None
    holding_cost_per_unit: Optional[float] = None

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    total_annual_cost: Optional[float] = None

def calculate_total_annual_inventory_cost(input_data: Input) -> Output:
    """
    Calculate the total annual cost of an inventory policy by summing
    ordering costs and carrying costs. This is the classical inventory
    cost trade-off model used in EOQ analysis.

    WHEN TO USE THIS SKILL:
    - Evaluating the total annual cost of a fixed-order-quantity inventory policy
    - Comparing ordering cost vs. carrying cost trade-offs for different order quantities
    - Computing the cost component needed for Economic Order Quantity (EOQ) optimization
    - Assessing whether increasing or decreasing order quantity improves cost efficiency
    - Building cost curves for inventory policy selection

    Inputs:
        input_data (Input): Pydantic model containing annual_demand, order_quantity, order_cost, holding_cost_per_unit.

    Returns:
        Output: Pydantic model with total_annual_cost.

    Raises:
        ValueError: If any input is missing or invalid.
    """
    # --- Input validation (mandatory) ---
    if input_data.annual_demand is None:
        raise ValueError("annual_demand is required and must be provided.")
    if input_data.order_quantity is None:
        raise ValueError("order_quantity is required and must be provided.")
    if input_data.order_cost is None:
        raise ValueError("order_cost is required and must be provided.")
    if input_data.holding_cost_per_unit is None:
        raise ValueError("holding_cost_per_unit is required and must be provided.")
    
    annual_demand = input_data.annual_demand
    order_quantity = input_data.order_quantity
    order_cost = input_data.order_cost
    holding_cost_per_unit = input_data.holding_cost_per_unit

    if annual_demand <= 0:
        raise ValueError(
            f"annual_demand must be positive, got {annual_demand}"
        )
    if order_quantity <= 0:
        raise ValueError(
            f"order_quantity must be positive, got {order_quantity}"
        )
    if order_cost < 0:
        raise ValueError(
            f"order_cost must be non-negative, got {order_cost}"
        )
    if holding_cost_per_unit < 0:
        raise ValueError(
            f"holding_cost_per_unit must be non-negative, got {holding_cost_per_unit}"
        )

    # --- Core calculation ---
    # Annual ordering cost: number of orders per year * cost per order
    annual_ordering_cost = (annual_demand / order_quantity) * order_cost

    # Annual carrying cost: average inventory * holding cost per unit
    annual_carrying_cost = (order_quantity / 2.0) * holding_cost_per_unit

    # Total annual inventory cost
    total_annual_cost = annual_ordering_cost + annual_carrying_cost

    return Output(total_annual_cost=total_annual_cost)