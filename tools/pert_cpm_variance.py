import math
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    critical_task_variances: Optional[List[float]] = None


class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    project_variance: float = 0.0
    project_standard_deviation: float = 0.0


def aggregate_critical_path_variance(input_data: Input) -> Output:
    """
    Aggregate task variances along the critical path to determine overall project
    variance and standard deviation for probability assessments.

    WHEN TO USE THIS SKILL:
    This skill should be used for project schedule risk analysis using Program
    Evaluation and Review Technique (PERT) or Critical Path Method (CPM). Use it
    when you have individual variance estimates for activities on the critical path
    and need to calculate overall project uncertainty measures for:
    - Estimating probability of completing a project by a target date
    - Quantifying overall project schedule uncertainty for Monte Carlo simulations
    - Supporting risk assessment and contingency planning in project management
    - Calculating confidence intervals for project completion times
    - Prioritizing risk mitigation efforts on high-variance critical path tasks

    Inputs:
    - critical_task_variances (List[float]): Variance estimates for tasks on the
      critical path. Each variance must be non-negative. Typical calculation:
      ((pessimistic - optimistic) / 6)^2 for PERT analysis.

    Output:
    - Output with fields:
      - project_variance: Sum of all critical task variances
      - project_standard_deviation: Square root of project variance

    Raises:
    - ValueError: If critical_task_variances is None or empty
    - ValueError: If any variance is negative or not a finite number
    """
    # Defensive programming: Input validation
    if input_data.critical_task_variances is None:
        raise ValueError("critical_task_variances cannot be None")
    
    if not input_data.critical_task_variances:
        raise ValueError("critical_task_variances cannot be empty")
    
    for i, variance in enumerate(input_data.critical_task_variances):
        if not isinstance(variance, (int, float)):
            raise ValueError(
                f"Variance at index {i} must be a number, got {type(variance).__name__}"
            )
        if not math.isfinite(variance):
            raise ValueError(f"Variance at index {i} must be finite, got {variance}")
        if variance < 0:
            raise ValueError(f"Variance at index {i} cannot be negative, got {variance}")
    
    # Calculate project variance as sum of all critical task variances
    project_variance = sum(input_data.critical_task_variances)
    
    # Calculate project standard deviation (sqrt is safe since variance >= 0)
    project_standard_deviation = math.sqrt(project_variance)
    
    return Output(
        project_variance=project_variance,
        project_standard_deviation=project_standard_deviation
    )
