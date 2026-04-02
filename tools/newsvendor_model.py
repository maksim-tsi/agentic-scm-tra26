import scipy.stats as stats
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


class Input(BaseModel):
    """
    Input schema for Newsvendor strategic outcome evaluation.
    """
    model_config = ConfigDict(strict=True)
    
    production_cost: float = 0.0
    selling_price: float = 0.0
    salvage_value: float = 0.0
    mean_demand: float = 0.0
    standard_deviation: Optional[float] = None
    
    @field_validator('production_cost', 'selling_price', 'salvage_value', 'mean_demand')
    @classmethod
    def validate_non_negative(cls, v: float, field_name: str) -> float:
        if v < 0:
            raise ValueError(f'{field_name} must be non-negative')
        return v
    
    @field_validator('mean_demand')
    @classmethod
    def validate_positive_mean_demand(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Mean demand must be positive')
        return v
    
    @field_validator('standard_deviation')
    @classmethod
    def validate_positive_standard_deviation(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError('Standard deviation must be positive if provided')
        return v


class Output(BaseModel):
    """
    Output schema for Newsvendor strategic outcome evaluation.
    """
    model_config = ConfigDict(strict=True)
    
    optimal_order_quantity: Optional[float] = None
    critical_ratio: float = 0.0
    strategic_insight: str = ""
    note: Optional[str] = None


def evaluate_newsvendor_strategy(input_data: Input) -> Output:
    """
    Evaluate the strategic outcome in a Newsvendor model when the overage cost 
    significantly exceeds the underage cost, resulting in optimal order quantity 
    below mean demand.
    
    WHEN TO USE THIS SKILL:
    This skill is used for inventory management decisions in single-period scenarios 
    such as perishable goods, fashion items, or one-time events. It helps determine 
    optimal order quantity when demand is uncertain and there are costs associated 
    with overstocking (overage) and understocking (underage). Specifically, it is 
    applicable when analyzing strategic implications of cost structures where overage 
    cost exceeds underage cost, leading to conservative ordering strategies below 
    mean demand. Use this for newsvendor model analysis, inventory optimization, 
    and risk-averse ordering decisions.
    
    Inputs:
    - production_cost (float): Cost to produce/purchase one unit (must be non-negative)
    - selling_price (float): Price at which one unit is sold (must be non-negative)
    - salvage_value (float): Value recovered from unsold units (must be non-negative)
    - mean_demand (float): Expected/average demand (must be positive)
    - standard_deviation (float, optional): Standard deviation of demand distribution
    
    Output:
    Output object containing:
    - optimal_order_quantity: Calculated optimal order quantity (if standard_deviation provided)
    - critical_ratio: Critical ratio Cu / (Cu + Co)
    - strategic_insight: Description of strategic outcome based on cost comparison
    - note: Additional information if standard_deviation not provided
    """
    # Extract validated input values
    production_cost = input_data.production_cost
    selling_price = input_data.selling_price
    salvage_value = input_data.salvage_value
    mean_demand = input_data.mean_demand
    standard_deviation = input_data.standard_deviation
    
    # Calculate underage and overage costs
    Cu = selling_price - production_cost
    Co = production_cost - salvage_value
    
    # Validate cost relationships
    if Cu <= 0:
        raise ValueError('Underage cost (selling_price - production_cost) must be positive for profitable scenario')
    
    # Critical ratio calculation with division by zero guard
    denominator = Cu + Co
    if denominator == 0:
        raise ValueError('Sum of underage and overage costs cannot be zero')
    
    critical_ratio = Cu / denominator
    
    # Determine strategic insight
    if Co > Cu:
        strategic_insight = 'Overage cost exceeds underage cost, so optimal order quantity is below mean demand for symmetric demand distributions.'
    else:
        strategic_insight = 'Underage cost exceeds or equals overage cost, so optimal order quantity is at or above mean demand.'
    
    # Prepare output
    output = Output(
        critical_ratio=critical_ratio,
        strategic_insight=strategic_insight
    )
    
    # Calculate optimal order quantity if standard deviation provided
    if standard_deviation is not None:
        try:
            Q_star = stats.norm.ppf(critical_ratio, loc=mean_demand, scale=standard_deviation)
            output.optimal_order_quantity = Q_star
        except Exception as e:
            raise ValueError(f'Error calculating optimal order quantity: {str(e)}')
    else:
        output.note = 'Standard deviation not provided; optimal order quantity not calculated. Provide standard_deviation for exact quantile calculation.'
    
    return output