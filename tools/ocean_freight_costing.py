from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    base_freight_rate: Optional[float] = None
    bunker_adjustment_factor: Optional[float] = None
    currency_adjustment_factor: Optional[float] = None
    terminal_handling_charge: Optional[float] = None
    other_surcharges: Optional[List[float]] = None


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    total_freight_cost: Optional[float] = None


def calculate_total_freight_cost(input_data: InputSchema) -> OutputSchema:
    """Calculate the total all-in ocean freight cost for transporting a container.

    This function aggregates the base freight rate and various applicable surcharges
    to determine the total cost for ocean freight transportation.

    WHEN TO USE THIS SKILL:
    Use this skill in supply chain management and logistics for estimating the total
    cost of shipping containers via ocean freight. It is applicable in cost analysis,
    contract negotiation, and budget planning for international trade and transportation.
    Use when you need to compute an all-in freight rate from a base rate plus multiple
    surcharges including bunker adjustment factor (baf), currency adjustment factor (caf),
    terminal handling charge (thc), and any other trade-specific surcharges.

    Inputs:
    - base_freight_rate (float): The base rate charged by the carrier for freight transportation.
    - bunker_adjustment_factor (float): Surcharge for fuel cost variations.
    - currency_adjustment_factor (float): Surcharge for currency exchange rate fluctuations.
    - terminal_handling_charge (float): Charge for handling at terminals.
    - other_surcharges (List[float]): Additional surcharges applicable to the trade.

    Returns:
    - OutputSchema with total_freight_cost (float): The aggregated total freight cost.

    Raises:
    - ValueError: If any monetary input is negative or if other_surcharges contains negative values.
    - ValueError: If required input fields are None.
    """
    # Validate required fields are not None
    if input_data.base_freight_rate is None:
        raise ValueError("base_freight_rate is required and cannot be None")
    if input_data.bunker_adjustment_factor is None:
        raise ValueError("bunker_adjustment_factor is required and cannot be None")
    if input_data.currency_adjustment_factor is None:
        raise ValueError("currency_adjustment_factor is required and cannot be None")
    if input_data.terminal_handling_charge is None:
        raise ValueError("terminal_handling_charge is required and cannot be None")
    if input_data.other_surcharges is None:
        raise ValueError("other_surcharges is required and cannot be None")
    
    # Input validation for non-negative monetary values
    if input_data.base_freight_rate < 0:
        raise ValueError("base_freight_rate must be non-negative")
    if input_data.bunker_adjustment_factor < 0:
        raise ValueError("bunker_adjustment_factor must be non-negative")
    if input_data.currency_adjustment_factor < 0:
        raise ValueError("currency_adjustment_factor must be non-negative")
    if input_data.terminal_handling_charge < 0:
        raise ValueError("terminal_handling_charge must be non-negative")
    
    # Validate other_surcharges list
    if not isinstance(input_data.other_surcharges, (list, tuple)):
        raise ValueError("other_surcharges must be a list or tuple")
    
    for idx, surcharge in enumerate(input_data.other_surcharges):
        if surcharge < 0:
            raise ValueError(f"Surcharge at index {idx} in other_surcharges must be non-negative")
    
    # Calculate total freight cost as sum of base rate and all surcharges
    total_freight_cost = (
        input_data.base_freight_rate
        + input_data.bunker_adjustment_factor
        + input_data.currency_adjustment_factor
        + input_data.terminal_handling_charge
        + sum(input_data.other_surcharges)
    )
    
    return OutputSchema(total_freight_cost=total_freight_cost)