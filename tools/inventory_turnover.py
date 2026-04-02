from pydantic import BaseModel, ConfigDict
from typing import Optional


class Input(BaseModel):
    """Input schema for inventory turnover calculation."""
    model_config = ConfigDict(strict=True)
    annual_sales: Optional[float] = None
    average_inventory_level: Optional[float] = None


class Output(BaseModel):
    """Output schema for inventory turnover calculation."""
    model_config = ConfigDict(strict=True)
    inventory_turnover: Optional[float] = None


def calculate_inventory_turnover(annual_sales: float, average_inventory_level: float) -> float:
    """
    Calculate the inventory turnover ratio to measure how efficiently a company
    manages its inventory relative to its sales volume.

    WHEN TO USE THIS SKILL:
    This skill is used when a supply chain analyst or inventory manager needs to:
    - Evaluate inventory management efficiency by measuring how often inventory is sold and replaced
    - Benchmark inventory performance against industry standards or historical data
    - Identify overstocking situations (low turnover) that tie up working capital
    - Detect potential understocking risks (very high turnover) that may lead to stockouts
    - Support decisions on order quantities, safety stock levels, and reorder points
    - Assess the impact of inventory policies on cash flow and holding costs
    - Compare inventory efficiency across product lines, warehouses, or time periods

    Common business problems this skill solves:
    - "How efficiently are we managing our inventory?"
    - "Are we holding too much inventory relative to our sales?"
    - "What is our inventory turnover and how does it compare to benchmarks?"
    - "Should we adjust our purchasing or production schedules based on turnover metrics?"

    Inputs:
    - annual_sales (float): The total annual sales revenue or cost of goods sold.
      Must be a non-negative number. Represents the flow of goods through inventory.
    - average_inventory_level (float): The average value of inventory held during the period.
      Must be a positive number to avoid division by zero. Calculated typically as
      (beginning inventory + ending inventory) / 2.

    Output:
    - inventory_turnover (float): The inventory turnover ratio calculated as
      annual_sales / average_inventory_level. Higher values indicate more efficient
      inventory management. A value of 0 indicates no sales. Typical values vary
      by industry but often range from 2 to 10+.

    Raises:
    - ValueError: If annual_sales is negative.
    - ValueError: If average_inventory_level is zero or negative (division by zero guard).
    """
    # Defensive programming: explicit input validation before computation
    if annual_sales is None:
        raise ValueError("annual_sales is required and cannot be None")
    if average_inventory_level is None:
        raise ValueError("average_inventory_level is required and cannot be None")
    if not isinstance(annual_sales, (int, float)):
        raise ValueError("annual_sales must be a numeric type")
    if not isinstance(average_inventory_level, (int, float)):
        raise ValueError("average_inventory_level must be a numeric type")
    if annual_sales < 0:
        raise ValueError("annual_sales must be non-negative")
    if average_inventory_level <= 0:
        raise ValueError("average_inventory_level must be positive to avoid division by zero")

    # Core calculation
    inventory_turnover = annual_sales / average_inventory_level
    return inventory_turnover
