from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import List, Dict, Any, Optional


class InventoryItem(BaseModel):
    """Schema for individual inventory item with cost and usage data."""
    model_config = ConfigDict(strict=True)
    
    unit_purchase_cost: float
    annual_demand: float
    
    @field_validator('unit_purchase_cost', 'annual_demand')
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        """Validate that cost and demand are non-negative."""
        if v < 0:
            raise ValueError('Must be non-negative')
        return v


class Input(BaseModel):
    """Input schema for ABC inventory categorization."""
    model_config = ConfigDict(strict=True)
    
    items: List[InventoryItem] = []
    a_threshold: float = 0.80
    b_threshold: float = 0.95
    
    @field_validator('a_threshold', 'b_threshold')
    @classmethod
    def validate_thresholds(cls, v: float) -> float:
        """Validate threshold values are within valid range."""
        if not (0.0 <= v <= 1.0):
            raise ValueError('Must be between 0.0 and 1.0')
        return v
    
    @model_validator(mode='after')
    def validate_threshold_order(self) -> 'Input':
        """Ensure A threshold is less than B threshold."""
        if self.b_threshold <= self.a_threshold:
            raise ValueError('b_threshold must be greater than a_threshold')
        return self


class CategorySummary(BaseModel):
    """Schema for category summary statistics."""
    model_config = ConfigDict(strict=True)
    
    count: int
    total_value: float
    percentage_of_total: float


class CategorizationResult(BaseModel):
    """Schema for individual item categorization result."""
    model_config = ConfigDict(strict=True)
    
    unit_purchase_cost: float
    annual_demand: float
    annual_cost_volume_usage: float
    abc_category: str
    cumulative_percentage: float


class Output(BaseModel):
    """Output schema for ABC inventory categorization."""
    model_config = ConfigDict(strict=True)
    
    items: List[CategorizationResult] = []
    category_summary: Dict[str, CategorySummary] = {}
    a_threshold: float = 0.0
    b_threshold: float = 0.0
    total_items: int = 0


def abc_inventory_categorization(input_data: Input) -> Output:
    """
    WHEN TO USE THIS SKILL:
    This skill is used when you need to classify inventory items into priority categories (A, B, C)
    based on their annual cost volume usage. This is essential for:
    - Prioritizing inventory management efforts and cycle count frequencies
    - Setting differentiated service levels and safety stock by category
    - Allocating warehouse space and procurement resources efficiently
    - Applying the Pareto principle to focus attention on high-value items
    - Determining appropriate inventory control policies for each segment
    - Optimizing inventory investment across product lines
    - Identifying critical items that require tighter control and monitoring
    
    Business Problems Solved:
    1. Inventory segmentation for differentiated management policies
    2. Resource allocation optimization for procurement and warehouse teams
    3. Service level differentiation based on item value contribution
    4. Cycle count scheduling prioritization
    5. Safety stock policy determination by item category
    6. Inventory investment optimization across product portfolios
    
    Inputs:
        input_data (Input): Contains:
            - items: List of inventory items with unit_purchase_cost and annual_demand
            - a_threshold: Cumulative percentage threshold for A category (default 0.80)
            - b_threshold: Cumulative percentage threshold for B category (default 0.95)
    
    Output:
        Output: Contains:
            - items: Categorized items with annual_cost_volume_usage, abc_category,
              and cumulative_percentage fields
            - category_summary: Summary statistics for A, B, C categories
            - a_threshold: Threshold used for A category
            - b_threshold: Threshold used for B category
            - total_items: Total number of items processed
    """
    # Defensive programming: Validate input
    if not input_data.items:
        raise ValueError("Items list cannot be empty")
    
    # Extract validated parameters
    items = input_data.items
    a_threshold = input_data.a_threshold
    b_threshold = input_data.b_threshold
    
    # Calculate annual cost volume usage for each item
    enriched_items = []
    for item in items:
        annual_cost_volume_usage = item.unit_purchase_cost * item.annual_demand
        enriched_items.append({
            'unit_purchase_cost': item.unit_purchase_cost,
            'annual_demand': item.annual_demand,
            'annual_cost_volume_usage': annual_cost_volume_usage
        })
    
    # Sort by annual_cost_volume_usage in descending order
    enriched_items.sort(key=lambda x: x['annual_cost_volume_usage'], reverse=True)
    
    # Calculate total annual cost volume usage
    total_value = sum(item['annual_cost_volume_usage'] for item in enriched_items)
    
    # Handle edge case where total value is zero
    if total_value == 0:
        categorized_items = []
        for item in enriched_items:
            categorized_items.append(CategorizationResult(
                unit_purchase_cost=item['unit_purchase_cost'],
                annual_demand=item['annual_demand'],
                annual_cost_volume_usage=item['annual_cost_volume_usage'],
                abc_category='C',
                cumulative_percentage=0.0
            ))
        
        category_summary = {
            'A': CategorySummary(count=0, total_value=0.0, percentage_of_total=0.0),
            'B': CategorySummary(count=0, total_value=0.0, percentage_of_total=0.0),
            'C': CategorySummary(count=len(categorized_items), total_value=0.0, percentage_of_total=0.0)
        }
        
        return Output(
            items=categorized_items,
            category_summary=category_summary,
            a_threshold=a_threshold,
            b_threshold=b_threshold,
            total_items=len(categorized_items)
        )
    
    # Assign ABC categories based on cumulative percentage
    cumulative_value = 0.0
    categorized_items = []
    
    for item in enriched_items:
        cumulative_value += item['annual_cost_volume_usage']
        cumulative_percentage = cumulative_value / total_value
        
        if cumulative_percentage <= a_threshold:
            abc_category = 'A'
        elif cumulative_percentage <= b_threshold:
            abc_category = 'B'
        else:
            abc_category = 'C'
        
        categorized_items.append(CategorizationResult(
            unit_purchase_cost=item['unit_purchase_cost'],
            annual_demand=item['annual_demand'],
            annual_cost_volume_usage=item['annual_cost_volume_usage'],
            abc_category=abc_category,
            cumulative_percentage=cumulative_percentage
        ))
    
    # Build category summary
    category_summary = {}
    for category in ['A', 'B', 'C']:
        category_items = [item for item in categorized_items if item.abc_category == category]
        category_total = sum(item.annual_cost_volume_usage for item in category_items)
        
        category_summary[category] = CategorySummary(
            count=len(category_items),
            total_value=category_total,
            percentage_of_total=category_total / total_value if total_value > 0 else 0.0
        )
    
    return Output(
        items=categorized_items,
        category_summary=category_summary,
        a_threshold=a_threshold,
        b_threshold=b_threshold,
        total_items=len(categorized_items)
    )