import math
from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    process_average_proportion_defective: float = 0.0
    sample_size: int = 1


class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    ucl_p: float = 0.0


def calculate_ucl_p_chart(input: Input) -> Output:
    """
    Calculate the Upper Control Limit (UCL_p) for a p-chart monitoring the proportion of defective orders.
    
    WHEN TO USE THIS SKILL:
    This skill is used in statistical process control to set control limits for p-charts, which monitor the proportion of nonconforming items or defective orders in a process. It is applicable in quality assurance, manufacturing, and service industries where tracking defect rates is critical for maintaining process stability and identifying out-of-control conditions. Specifically, it helps in quality control decision-making by computing the upper boundary for acceptable proportion defective based on historical data.
    
    Inputs:
    - process_average_proportion_defective (float): The average proportion of defective items in the process, denoted as p̄. Must be between 0 and 1 inclusive.
    - sample_size (int): The constant sample size used in each subgroup, denoted as n. Must be a positive integer.
    
    Output:
    - Output: A Pydantic model containing the Upper Control Limit (UCL_p) for the p-chart.
    
    Formula: UCL_p = p̄ + 3 * sqrt[p̄(1 - p̄) / n]
    """
    # Input validation
    if input.process_average_proportion_defective < 0 or input.process_average_proportion_defective > 1:
        raise ValueError("process_average_proportion_defective must be between 0 and 1")
    if input.sample_size <= 0:
        raise ValueError("sample_size must be a positive integer")
    
    # Calculate standard error and UCL
    standard_error = math.sqrt(
        input.process_average_proportion_defective * (1 - input.process_average_proportion_defective) / input.sample_size
    )
    ucl_p = input.process_average_proportion_defective + 3 * standard_error
    
    return Output(ucl_p=ucl_p)