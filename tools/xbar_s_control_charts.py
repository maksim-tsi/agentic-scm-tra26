from pydantic import BaseModel, ConfigDict
from typing import List, Optional

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    
    sample_means: Optional[List[float]] = None
    sample_standard_deviations: Optional[List[float]] = None
    num_samples: Optional[int] = None
    b3_factor: Optional[float] = None
    b4_factor: Optional[float] = None
    a3_factor: Optional[float] = None

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    
    grand_mean: Optional[float] = None
    average_s: Optional[float] = None
    ucl_s: Optional[float] = None
    lcl_s: Optional[float] = None
    ucl_x: Optional[float] = None
    lcl_x: Optional[float] = None

def calculate_control_limits(input: Input) -> Output:
    """
    WHEN TO USE THIS SKILL:
    This skill is used to calculate control limits for X-bar and S charts in statistical process control (SPC).
    It is specifically applied when monitoring process mean and dispersion, and when range charts are insufficient for precise dispersion monitoring.
    Use this skill in quality control settings to establish control limits for process monitoring, detect out-of-control conditions, and maintain process stability in supply chain manufacturing processes.

    Inputs:
    - input: An Input object containing:
        - sample_means: List of sample means (floats), each representing the average of a subgroup.
        - sample_standard_deviations: List of sample standard deviations (floats), each representing the standard deviation of a subgroup.
        - num_samples: Integer number of samples (subgroups), must match the length of sample_means and sample_standard_deviations.
        - b3_factor: Float, control limit factor for LCL of S chart, typically from SPC tables based on sample size.
        - b4_factor: Float, control limit factor for UCL of S chart, typically from SPC tables.
        - a3_factor: Float, control limit factor for X-bar chart, typically from SPC tables.

    Output:
    An Output object with fields:
    - grand_mean: The overall mean of sample means.
    - average_s: The average of sample standard deviations.
    - ucl_s: Upper control limit for S chart.
    - lcl_s: Lower control limit for S chart.
    - ucl_x: Upper control limit for X-bar chart.
    - lcl_x: Lower control limit for X-bar chart.
    """
    # Input validation
    if input.sample_means is None:
        raise ValueError("sample_means must be provided.")
    if input.sample_standard_deviations is None:
        raise ValueError("sample_standard_deviations must be provided.")
    if input.num_samples is None:
        raise ValueError("num_samples must be provided.")
    if input.b3_factor is None:
        raise ValueError("b3_factor must be provided.")
    if input.b4_factor is None:
        raise ValueError("b4_factor must be provided.")
    if input.a3_factor is None:
        raise ValueError("a3_factor must be provided.")
    
    sample_means = input.sample_means
    sample_standard_deviations = input.sample_standard_deviations
    num_samples = input.num_samples
    b3_factor = input.b3_factor
    b4_factor = input.b4_factor
    a3_factor = input.a3_factor
    
    # Type and value validation
    if not isinstance(sample_means, list) or not isinstance(sample_standard_deviations, list):
        raise ValueError("sample_means and sample_standard_deviations must be lists.")
    if len(sample_means) != len(sample_standard_deviations):
        raise ValueError("sample_means and sample_standard_deviations must have the same length.")
    if not isinstance(num_samples, int) or num_samples <= 0:
        raise ValueError("num_samples must be a positive integer.")
    if num_samples != len(sample_means):
        raise ValueError("num_samples must match the length of sample_means and sample_standard_deviations.")
    if any(not isinstance(x, (int, float)) for x in sample_means) or any(not isinstance(x, (int, float)) for x in sample_standard_deviations):
        raise ValueError("All elements in sample_means and sample_standard_deviations must be numbers.")
    if any(x < 0 for x in sample_means) or any(x < 0 for x in sample_standard_deviations):
        raise ValueError("sample_means and sample_standard_deviations must not contain negative values.")
    if not all(isinstance(factor, (int, float)) for factor in [b3_factor, b4_factor, a3_factor]):
        raise ValueError("b3_factor, b4_factor, and a3_factor must be numbers.")
    if b3_factor < 0 or b4_factor < 0 or a3_factor < 0:
        raise ValueError("b3_factor, b4_factor, and a3_factor must be non-negative.")
    
    # Compute grand_mean and average_s
    grand_mean = sum(sample_means) / num_samples
    average_s = sum(sample_standard_deviations) / num_samples
    
    # Compute control limits
    ucl_s = b4_factor * average_s
    lcl_s = b3_factor * average_s
    ucl_x = grand_mean + (a3_factor * average_s)
    lcl_x = grand_mean - (a3_factor * average_s)
    
    # Return Output object
    return Output(
        grand_mean=grand_mean,
        average_s=average_s,
        ucl_s=ucl_s,
        lcl_s=lcl_s,
        ucl_x=ucl_x,
        lcl_x=lcl_x
    )