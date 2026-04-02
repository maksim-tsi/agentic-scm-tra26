import math
from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    average_demand: float = 0.0
    std_dev_demand: float = 0.0
    average_lead_time: float = 0.0
    std_dev_lead_time: float = 0.0
    safety_factor_z: float = 0.0

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    reorder_point: float = 0.0
    safety_stock: float = 0.0

def calculate_reorder_point_safety_stock(input_params: Input) -> Output:
    """
    Calculate reorder point and safety stock when demand and lead time are random and normally distributed.

    WHEN TO USE THIS SKILL:
    This skill is used in inventory management and scheduling when both customer demand and supplier lead times are uncertain. 
    It helps determine the reorder point and safety stock to maintain desired service levels, reducing stockout risks while optimizing inventory costs.
    Applicable in scenarios where demand variability and lead time variability need to be considered together, such as in continuous review systems with stochastic elements.

    Inputs:
    - average_demand: Average demand per unit time. Must be a positive number.
    - std_dev_demand: Standard deviation of demand. Must be a non-negative number.
    - average_lead_time: Average lead time for replenishment. Must be a positive number.
    - std_dev_lead_time: Standard deviation of lead time. Must be a non-negative number.
    - safety_factor_z: Safety factor (z-score) for the desired service level. Must be a non-negative number.

    Output:
    Output object with fields:
    - reorder_point: The inventory level at which a new order should be placed.
    - safety_stock: The extra inventory held to buffer against uncertainties.
    """
    # Input validation
    if input_params.average_demand <= 0:
        raise ValueError("average_demand must be a positive number.")
    if input_params.std_dev_demand < 0:
        raise ValueError("std_dev_demand must be a non-negative number.")
    if input_params.average_lead_time <= 0:
        raise ValueError("average_lead_time must be a positive number.")
    if input_params.std_dev_lead_time < 0:
        raise ValueError("std_dev_lead_time must be a non-negative number.")
    if input_params.safety_factor_z < 0:
        raise ValueError("safety_factor_z must be a non-negative number.")
    
    # Calculate safety stock
    variance_demand = input_params.std_dev_demand ** 2
    variance_lead_time = input_params.std_dev_lead_time ** 2
    inside_sqrt = (input_params.average_lead_time * variance_demand) + (input_params.average_demand ** 2 * variance_lead_time)
    safety_stock = input_params.safety_factor_z * math.sqrt(inside_sqrt)
    
    # Calculate reorder point
    reorder_point = (input_params.average_demand * input_params.average_lead_time) + safety_stock
    
    return Output(reorder_point=reorder_point, safety_stock=safety_stock)