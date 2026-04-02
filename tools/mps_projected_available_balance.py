from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    initial_projected_available_balance: float = Field(
        default=0.0,
        description="The starting PAB (before period 1)"
    )
    forecast_per_period: List[float] = Field(
        default_factory=list,
        description="Forecasted demand for each period"
    )
    customer_orders_per_period: List[float] = Field(
        default_factory=list,
        description="Committed customer orders for each period"
    )
    mps_receipts_per_period: List[float] = Field(
        default_factory=list,
        description="Scheduled MPS receipts for each period"
    )
    target_period: int = Field(
        default=1,
        description="The period (1-indexed) for which to compute the PAB"
    )


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    projected_available_balance: float = Field(
        default=0.0,
        description="The Projected Available Balance at the end of the target period"
    )


def compute_projected_available_balance(
    initial_projected_available_balance: float,
    forecast_per_period: List[float],
    customer_orders_per_period: List[float],
    mps_receipts_per_period: List[float],
    target_period: int
) -> OutputSchema:
    """
    Compute the Projected Available Balance (PAB) for a specific period in the Master Production Schedule.

    WHEN TO USE THIS SKILL:
    This skill calculates the projected inventory level after accounting for scheduled production (MPS receipts)
    and demand (the greater of forecast or customer orders) for each period. It is used in master planning to
    determine if planned production meets demand and to identify potential stockouts or excess inventory.
    The output is the PAB for the target period.

    Business applications:
    - Master Production Schedule (MPS) validation
    - Inventory planning and control
    - Identifying periods of potential stockouts or excess inventory
    - Evaluating production schedule feasibility

    Inputs:
        initial_projected_available_balance (float): The starting PAB (before period 1).
        forecast_per_period (list of float): Forecasted demand for each period.
        customer_orders_per_period (list of float): Committed customer orders for each period.
        mps_receipts_per_period (list of float): Scheduled MPS receipts for each period.
        target_period (int): The period (1-indexed) for which to compute the PAB.

    Returns:
        OutputSchema: Object containing the Projected Available Balance at the end of the target period.

    Raises:
        ValueError: If input lists are not of equal length, if target_period is invalid,
                   if lists are too short, or if any values are negative.
    """
    # Input validation
    if not isinstance(target_period, int) or target_period < 1:
        raise ValueError("target_period must be a positive integer (>=1).")
    
    if initial_projected_available_balance < 0:
        raise ValueError("initial_projected_available_balance cannot be negative.")
    
    # Validate list lengths
    if len(forecast_per_period) < target_period:
        raise ValueError("forecast_per_period must have at least target_period elements.")
    if len(customer_orders_per_period) < target_period:
        raise ValueError("customer_orders_per_period must have at least target_period elements.")
    if len(mps_receipts_per_period) < target_period:
        raise ValueError("mps_receipts_per_period must have at least target_period elements.")
    
    # Ensure all lists have the same length
    if not (len(forecast_per_period) == len(customer_orders_per_period) == len(mps_receipts_per_period)):
        raise ValueError("forecast_per_period, customer_orders_per_period, and mps_receipts_per_period must have the same length.")
    
    # Validate list contents
    for i, (forecast, orders, receipts) in enumerate(zip(forecast_per_period, customer_orders_per_period, mps_receipts_per_period)):
        if forecast < 0:
            raise ValueError(f"forecast_per_period contains negative value at index {i}.")
        if orders < 0:
            raise ValueError(f"customer_orders_per_period contains negative value at index {i}.")
        if receipts < 0:
            raise ValueError(f"mps_receipts_per_period contains negative value at index {i}.")
    
    # Initialize PAB
    pab = initial_projected_available_balance
    
    # Iterate through periods up to target_period
    for period_index in range(target_period):
        demand = max(forecast_per_period[period_index], customer_orders_per_period[period_index])
        pab = pab + mps_receipts_per_period[period_index] - demand
    
    return OutputSchema(projected_available_balance=pab)