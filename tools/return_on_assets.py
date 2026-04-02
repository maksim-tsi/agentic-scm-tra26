from pydantic import BaseModel, ConfigDict
from typing import Optional


class InputSchema(BaseModel):
    """Input schema for ROA calculation."""
    model_config = ConfigDict(strict=True)
    
    net_income_current_year: Optional[float] = None
    total_assets_previous_year: Optional[float] = None
    total_assets_current_year: Optional[float] = None


class OutputSchema(BaseModel):
    """Output schema for ROA calculation."""
    model_config = ConfigDict(strict=True)
    
    return_on_total_assets: Optional[float] = None


def calculate_return_on_total_assets(input_data: InputSchema) -> OutputSchema:
    """
    Calculate Return on Total Assets (ROA) for a given year using current net income
    divided by the average total assets from the previous and current years.
    
    WHEN TO USE THIS SKILL:
    Use this skill to compute the Return on Total Assets (ROA) metric, which measures
    a company's profitability relative to its total assets. This is useful in financial
    analysis for assessing how efficiently a company is using its assets to generate
    earnings. Apply this skill when evaluating company performance, comparing asset
    utilization across periods, or benchmarking against industry standards.
    
    Inputs:
    - net_income_current_year (float): Net income for the current year.
    - total_assets_previous_year (float): Total assets from the previous year.
    - total_assets_current_year (float): Total assets for the current year.
    
    Output:
    - OutputSchema with return_on_total_assets (float): ROA value rounded to two decimal places.
    """
    # Extract values from input
    net_income_current_year = input_data.net_income_current_year
    total_assets_previous_year = input_data.total_assets_previous_year
    total_assets_current_year = input_data.total_assets_current_year
    
    # Input validation - check for None values
    if net_income_current_year is None:
        raise ValueError("net_income_current_year is required and cannot be None.")
    if total_assets_previous_year is None:
        raise ValueError("total_assets_previous_year is required and cannot be None.")
    if total_assets_current_year is None:
        raise ValueError("total_assets_current_year is required and cannot be None.")
    
    # Validate inputs are numeric
    if not isinstance(net_income_current_year, (int, float)):
        raise ValueError("net_income_current_year must be numeric (int or float).")
    if not isinstance(total_assets_previous_year, (int, float)):
        raise ValueError("total_assets_previous_year must be numeric (int or float).")
    if not isinstance(total_assets_current_year, (int, float)):
        raise ValueError("total_assets_current_year must be numeric (int or float).")
    
    # Calculate average total assets
    average_total_assets = (total_assets_previous_year + total_assets_current_year) / 2
    
    # Guard against division by zero
    if average_total_assets == 0:
        raise ValueError("Average total assets cannot be zero for ROA calculation.")
    
    # Compute ROA
    roa = net_income_current_year / average_total_assets
    
    # Round to two decimal places and return
    return OutputSchema(return_on_total_assets=round(roa, 2))