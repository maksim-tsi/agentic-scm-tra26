import math
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    time_periods: Optional[List[float]] = None
    actual_demands: Optional[List[float]] = None
    forecast_period: Optional[float] = None


class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    forecast_x: float = 0.0
    standard_error: float = 0.0
    slope_b: float = 0.0
    intercept_a: float = 0.0
    avg_time: float = 0.0
    avg_demand: float = 0.0
    num_periods: int = 0


def linear_trend_forecast(input: Input) -> Output:
    """
    Calculate linear trend forecast using least squares regression based on historical demand data.

    WHEN TO USE THIS SKILL:
    This skill is used for forecasting future aggregate demand when historical demand exhibits a linear trend over time.
    It applies least squares regression to identify and project trends, enabling businesses to make informed decisions in:
    - Production planning and scheduling by anticipating future demand levels
    - Inventory management and replenishment planning to optimize stock levels
    - Sales and operations planning (S&OP) for aligning supply with projected demand
    - Budgeting and financial forecasting based on demand-driven revenue estimates
    - Capacity planning to ensure resources meet future demand requirements
    The skill is ideal for time-series data with a clear linear pattern and requires at least two historical data points.

    Parameters:
    input (Input): Pydantic model containing:
        - time_periods (List[float]): Historical time periods (e.g., months, quarters, years), must be non-empty and numeric.
        - actual_demands (List[float]): Corresponding actual demand values, must match length of time_periods and be numeric.
        - forecast_period (float): Future time period for which to generate the forecast, must be numeric.

    Returns:
    Output: Pydantic model with forecast results including:
        - forecast_x: Forecasted demand for the specified period
        - standard_error: Standard error of the regression estimate
        - slope_b: Slope coefficient of the regression line
        - intercept_a: Intercept coefficient of the regression line
        - avg_time: Average of time periods
        - avg_demand: Average of actual demands
        - num_periods: Number of historical data points

    Raises:
    ValueError: If inputs are invalid (e.g., empty lists, mismatched lengths, insufficient data points, non-numeric values, or identical time periods causing division by zero).
    """
    # Extract inputs
    time_periods = input.time_periods
    actual_demands = input.actual_demands
    forecast_period = input.forecast_period

    # Defensive input validation
    if time_periods is None or actual_demands is None or forecast_period is None:
        raise ValueError("time_periods, actual_demands, and forecast_period must be provided")
    
    if not isinstance(time_periods, list) or not isinstance(actual_demands, list):
        raise ValueError("time_periods and actual_demands must be lists")
    
    if len(time_periods) == 0 or len(actual_demands) == 0:
        raise ValueError("time_periods and actual_demands cannot be empty")
    
    if len(time_periods) != len(actual_demands):
        raise ValueError("time_periods and actual_demands must have the same length")
    
    num_periods = len(time_periods)
    if num_periods < 2:
        raise ValueError("At least 2 data points are required for linear regression")
    
    # Check for numeric values
    for i, t in enumerate(time_periods):
        if not isinstance(t, (int, float)):
            raise ValueError(f"time_periods[{i}] must be numeric, got {type(t)}")
    for i, d in enumerate(actual_demands):
        if not isinstance(d, (int, float)):
            raise ValueError(f"actual_demands[{i}] must be numeric, got {type(d)}")
    if not isinstance(forecast_period, (int, float)):
        raise ValueError("forecast_period must be numeric")
    
    # Compute sums for regression
    sum_time = sum(time_periods)
    sum_demand = sum(actual_demands)
    sum_time_squared = sum(t * t for t in time_periods)
    sum_time_demand = sum(t * d for t, d in zip(time_periods, actual_demands))
    
    # Calculate averages
    avg_time = sum_time / num_periods
    avg_demand = sum_demand / num_periods
    
    # Calculate slope and intercept
    denominator = sum_time_squared - (num_periods * avg_time * avg_time)
    if denominator == 0:
        raise ValueError("Cannot compute regression: all time periods are identical, leading to division by zero")
    
    slope_b = (sum_time_demand - (num_periods * avg_time * avg_demand)) / denominator
    intercept_a = avg_demand - (slope_b * avg_time)
    
    # Forecast for the specified period
    forecast_x = intercept_a + (slope_b * forecast_period)
    
    # Calculate standard error of the estimate
    sum_squared_errors = 0.0
    for t, d in zip(time_periods, actual_demands):
        predicted = intercept_a + (slope_b * t)
        error = d - predicted
        sum_squared_errors += error * error
    
    if num_periods == 2:
        standard_error = 0.0  # Perfect fit with two points
    else:
        standard_error = math.sqrt(sum_squared_errors / (num_periods - 2))
    
    # Return output
    return Output(
        forecast_x=forecast_x,
        standard_error=standard_error,
        slope_b=slope_b,
        intercept_a=intercept_a,
        avg_time=avg_time,
        avg_demand=avg_demand,
        num_periods=num_periods
    )