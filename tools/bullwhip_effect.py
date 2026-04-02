import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    end_customer_demand: Optional[List[float]] = None
    order_volatility: Optional[float] = None
    local_optimization_objectives: Optional[str] = None
    supply_chain_coordination_level: Optional[float] = None
    
    @field_validator('end_customer_demand')
    @classmethod
    def validate_end_customer_demand(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        if len(v) == 0:
            raise ValueError("end_customer_demand must be a non-empty list.")
        if any(demand <= 0 for demand in v):
            raise ValueError("All elements in end_customer_demand must be positive.")
        return v
    
    @field_validator('order_volatility')
    @classmethod
    def validate_order_volatility(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0:
            raise ValueError("order_volatility must be non-negative.")
        return v
    
    @field_validator('supply_chain_coordination_level')
    @classmethod
    def validate_supply_chain_coordination_level(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if not (0.0 <= v <= 1.0):
            raise ValueError("supply_chain_coordination_level must be between 0.0 and 1.0.")
        return v


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    bullwhip_ratio: Optional[float] = None
    demand_variability: Optional[float] = None
    adjusted_order_volatility: Optional[float] = None
    coordination_impact: Optional[float] = None


def bullwhip_effect_identifier(input_data: InputSchema) -> OutputSchema:
    """
    WHEN TO USE THIS SKILL:
    This skill identifies and quantifies the bullwhip effect in supply chains caused by sequential local optimization. 
    It helps analyze supply chain integration failures where demand variability is amplified upstream due to independent 
    decision-making at each echelon (such as batch ordering, promotion buying, or forecast updating). Use this skill when:
    - Evaluating order volatility amplification across supply chain echelons
    - Diagnosing coordination failures between supply chain partners
    - Designing strategies to reduce bullwhip effect through improved coordination
    - Comparing different local optimization objectives and their impact on system-wide variability
    - Quantifying the benefits of supply chain coordination initiatives
    
    Inputs:
    - end_customer_demand: List of positive floats representing customer demand over time periods
    - order_volatility: Non-negative float representing upstream order variability (e.g., standard deviation)
    - local_optimization_objectives: String describing local optimization behavior ('batch_ordering', 'promotion_buying', or other)
    - supply_chain_coordination_level: Float between 0.0 and 1.0 indicating coordination level (1.0 = full coordination)
    
    Output:
    OutputSchema containing:
    - bullwhip_ratio: Float indicating demand amplification factor (>1.0 indicates bullwhip effect)
    - demand_variability: Float representing standard deviation of customer demand
    - adjusted_order_volatility: Float representing coordination-adjusted order variability
    - coordination_impact: Float representing reduction in bullwhip ratio due to coordination
    """
    # Extract and validate inputs
    if input_data.end_customer_demand is None:
        raise ValueError("end_customer_demand is required.")
    if input_data.order_volatility is None:
        raise ValueError("order_volatility is required.")
    if input_data.local_optimization_objectives is None:
        raise ValueError("local_optimization_objectives is required.")
    if input_data.supply_chain_coordination_level is None:
        raise ValueError("supply_chain_coordination_level is required.")
    
    demand_array = np.array(input_data.end_customer_demand)
    
    # Compute demand variability
    demand_variability = np.std(demand_array)
    if demand_variability == 0:
        raise ValueError("Demand variability is zero; cannot compute bullwhip ratio.")
    
    # Define coordination effectiveness based on local optimization objectives
    if input_data.local_optimization_objectives == 'batch_ordering':
        coordination_effectiveness = 0.8
    elif input_data.local_optimization_objectives == 'promotion_buying':
        coordination_effectiveness = 0.6
    else:
        coordination_effectiveness = 0.7
    
    # Compute base bullwhip ratio
    base_ratio = input_data.order_volatility / demand_variability
    
    # Adjust ratio based on coordination level
    adjusted_ratio = base_ratio * (1 - input_data.supply_chain_coordination_level * coordination_effectiveness)
    adjusted_ratio = max(1.0, adjusted_ratio)  # Ensure at least 1.0 for amplification
    
    # Compute additional metrics
    adjusted_order_volatility = adjusted_ratio * demand_variability
    coordination_impact = base_ratio - adjusted_ratio
    
    return OutputSchema(
        bullwhip_ratio=adjusted_ratio,
        demand_variability=demand_variability,
        adjusted_order_volatility=adjusted_order_volatility,
        coordination_impact=coordination_impact
    )