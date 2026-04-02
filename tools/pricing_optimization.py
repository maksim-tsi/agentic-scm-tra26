from pydantic import BaseModel, ConfigDict
from typing import Dict, Any


class InputSchema(BaseModel):
    """Input schema for optimal retail pricing calculation."""
    model_config = ConfigDict(strict=True)
    
    demand_intercept: float = 0.0
    demand_slope: float = 0.0
    wholesale_price: float = 0.0


class OutputSchema(BaseModel):
    """Output schema for optimal retail pricing calculation."""
    model_config = ConfigDict(strict=True)
    
    optimal_retail_price: float = 0.0
    realized_customer_demand: float = 0.0
    retailer_profit: float = 0.0
    retailer_margin: float = 0.0
    discount_pass_through_rate: float = 0.0


def optimal_retail_pricing(input_data: InputSchema) -> OutputSchema:
    """
    Determine the optimal retail price a retailer should set when given a supplier
    discount, assuming a downward-sloping linear customer demand curve, to map how
    much discount is passed through to end customers.

    WHEN TO USE THIS SKILL:
    - Pricing optimization for retailers facing linear demand curves
    - Analyzing supplier discount pass-through to consumer prices
    - Determining profit-maximizing retail price given wholesale cost
    - Evaluating how changes in wholesale price affect retail pricing strategy
    - Quantifying retailer margin and realized demand at optimal price
    - Assessing channel coordination and double marginalization effects
    - Calculating price elasticity implications for demand functions

    Inputs:
        demand_intercept (float): The intercept of the linear demand curve (maximum
            demand when price is zero). Must be positive.
        demand_slope (float): The slope of the linear demand curve (rate of demand
            decrease per unit price increase). Must be positive for downward-sloping demand.
        wholesale_price (float): The wholesale price charged by the supplier to the
            retailer. Must be non-negative.

    Output:
        OutputSchema: Contains optimal_retail_price, realized_customer_demand, 
                      retailer_profit, retailer_margin, and discount_pass_through_rate.
    """
    # --- Input Validation ---
    if input_data.demand_intercept <= 0:
        raise ValueError(
            f"demand_intercept must be positive, got {input_data.demand_intercept}"
        )

    if input_data.demand_slope <= 0:
        raise ValueError(
            f"demand_slope must be positive for downward-sloping demand, got {input_data.demand_slope}"
        )

    if input_data.wholesale_price < 0:
        raise ValueError(
            f"wholesale_price must be non-negative, got {input_data.wholesale_price}"
        )

    # Validate that wholesale price allows positive retail price and demand
    max_viable_wholesale = input_data.demand_intercept / input_data.demand_slope
    if input_data.wholesale_price >= max_viable_wholesale:
        raise ValueError(
            f"wholesale_price ({input_data.wholesale_price}) must be less than demand_intercept/demand_slope "
            f"({max_viable_wholesale:.4f}) for viable retail pricing"
        )

    # --- Core Calculations ---
    # Optimal retail price from first-order condition of profit maximization
    optimal_price = (
        input_data.demand_intercept + input_data.demand_slope * input_data.wholesale_price
    ) / (2 * input_data.demand_slope)

    # Realized customer demand at optimal price
    realized_demand = input_data.demand_intercept - input_data.demand_slope * optimal_price

    # Retailer margin and profit at optimal price
    margin = optimal_price - input_data.wholesale_price
    profit = realized_demand * margin

    # Discount pass-through rate (from calculus: d(retail_price)/d(wholesale_price) = 0.5)
    pass_through = 0.5

    return OutputSchema(
        optimal_retail_price=round(optimal_price, 4),
        realized_customer_demand=round(realized_demand, 4),
        retailer_profit=round(profit, 4),
        retailer_margin=round(margin, 4),
        discount_pass_through_rate=pass_through
    )