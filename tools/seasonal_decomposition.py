from pydantic import BaseModel, ConfigDict, Field
from typing import List
import numpy as np

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    actual_demand_series: List[float] = Field(default_factory=list)
    periods_per_season: int = Field(default=2)
    trend_forecasts: List[float] = Field(default_factory=list)

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    seasonal_factors: List[float] = Field(default_factory=list)
    deseasonalized_demand: List[float] = Field(default_factory=list)
    seasonal_forecasts: List[float] = Field(default_factory=list)

def calculate_seasonal_indices(input: Input) -> Output:
    """
    Calculate seasonal indices from historical demand data, deseasonalize the historical demand,
    and generate seasonal forecasts by applying indices to trend forecasts.

    WHEN TO USE THIS SKILL:
    This skill is used for time series decomposition and forecasting when demand exhibits
    repeating seasonal patterns. Use when you need to:
    1. Isolate and measure seasonal variations in historical demand
    2. Remove seasonal effects to analyze underlying trends
    3. Project future demand by combining trend forecasts with seasonal patterns
    Common applications: inventory planning, sales forecasting, production scheduling,
    and demand sensing for products with predictable seasonal cycles (e.g., holiday items,
    weather-dependent products, back-to-school supplies).

    Args:
        input (Input): Contains actual_demand_series, periods_per_season, and trend_forecasts.

    Returns:
        Output: Contains seasonal_factors, deseasonalized_demand, and seasonal_forecasts.

    Raises:
        ValueError: If input validation fails (e.g., empty series, invalid lengths, division by zero).
    """
    # Extract inputs
    actual_demand_series = input.actual_demand_series
    periods_per_season = input.periods_per_season
    trend_forecasts = input.trend_forecasts
    
    # ==================== INPUT VALIDATION ====================
    if not actual_demand_series:
        raise ValueError("actual_demand_series cannot be empty")
    if any(demand < 0 for demand in actual_demand_series):
        raise ValueError("All demand values must be non-negative")
    if len(actual_demand_series) < 2 * periods_per_season:
        raise ValueError(f"Need at least 2 complete seasons ({2 * periods_per_season} periods) of demand data. Got {len(actual_demand_series)} periods.")
    if periods_per_season < 2:
        raise ValueError("periods_per_season must be at least 2")
    if not trend_forecasts:
        raise ValueError("trend_forecasts cannot be empty")
    if len(trend_forecasts) != periods_per_season:
        raise ValueError(f"trend_forecasts length ({len(trend_forecasts)}) must equal periods_per_season ({periods_per_season})")
    if any(forecast <= 0 for forecast in trend_forecasts):
        raise ValueError("All trend forecasts must be positive")
    if len(actual_demand_series) % periods_per_season != 0:
        raise ValueError(f"Length of actual_demand_series ({len(actual_demand_series)}) must be divisible by periods_per_season ({periods_per_season})")
    
    # ==================== CALCULATION ====================
    num_seasons = len(actual_demand_series) // periods_per_season
    demand_matrix = np.array(actual_demand_series).reshape(num_seasons, periods_per_season)
    avg_demand_per_period = np.mean(demand_matrix, axis=0)
    avg_demand_all_periods = np.mean(actual_demand_series)
    
    if avg_demand_all_periods == 0:
        raise ValueError("Average demand across all periods is zero. Cannot calculate seasonal factors.")
    
    seasonal_factors = avg_demand_per_period / avg_demand_all_periods
    
    if any(factor <= 0 for factor in seasonal_factors):
        raise ValueError("Calculated seasonal factors must be positive. Check demand data for anomalies.")
    
    deseasonalized_demand = []
    for i, demand in enumerate(actual_demand_series):
        period_index = i % periods_per_season
        seasonal_factor = seasonal_factors[period_index]
        deseasonalized_demand.append(demand / seasonal_factor)
    
    seasonal_forecasts = [trend_forecasts[i] * seasonal_factors[i] for i in range(periods_per_season)]
    
    return Output(
        seasonal_factors=seasonal_factors.tolist(),
        deseasonalized_demand=deseasonalized_demand,
        seasonal_forecasts=seasonal_forecasts
    )