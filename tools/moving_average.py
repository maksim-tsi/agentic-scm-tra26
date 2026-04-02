from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    n_periods: Optional[int] = None
    historical_demand_t_minus_i: Optional[List[float]] = None

class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    forecast_t: float = 0.0

def moving_average_forecast(input_data: InputSchema) -> OutputSchema:
    """
    Calculate the forecast for future demand using a simple moving average of historical demand.

    WHEN TO USE THIS SKILL:
    This skill is used when you need to forecast future demand based on historical data by averaging the most recent demand periods. It is applicable in inventory management, demand planning, and supply chain optimization to smooth out random fluctuations and predict future demand trends. Use this skill when you have historical demand data and want a straightforward forecast method without complex modeling.

    Inputs:
    - n_periods (int): The number of recent historical periods to average. Must be a positive integer.
    - historical_demand_t_minus_i (List[float]): A list of historical demand values, ordered from oldest to newest. The list must have at least n_periods elements, and all values should be non-negative.

    Output:
    - forecast_t (float): The forecasted demand for the next period, calculated as the average of the last n_periods historical demand values.
    """
    # Input validation
    if input_data.n_periods is None:
        raise ValueError("n_periods must be provided.")
    if input_data.historical_demand_t_minus_i is None:
        raise ValueError("historical_demand_t_minus_i must be provided.")
    if not isinstance(input_data.n_periods, int) or input_data.n_periods <= 0:
        raise ValueError("n_periods must be a positive integer.")
    if not input_data.historical_demand_t_minus_i:
        raise ValueError("historical_demand_t_minus_i cannot be empty.")
    if len(input_data.historical_demand_t_minus_i) < input_data.n_periods:
        raise ValueError(f"historical_demand_t_minus_i must have at least {input_data.n_periods} elements, but has {len(input_data.historical_demand_t_minus_i)}.")
    for demand in input_data.historical_demand_t_minus_i:
        if demand < 0:
            raise ValueError("All historical demand values must be non-negative.")
    
    # Calculate the forecast: average of the last n_periods elements
    last_n_demands = input_data.historical_demand_t_minus_i[-input_data.n_periods:]
    forecast_t = sum(last_n_demands) / input_data.n_periods
    
    return OutputSchema(forecast_t=forecast_t)