import math
from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    number_of_product_configurations: int = 2
    demand_standard_deviation_per_configuration: float = 10.0
    average_demand_per_configuration: float = 100.0
    target_service_level: float = 0.95

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    individual_safety_stock_factor: float = 0.0
    aggregated_safety_stock_factor: float = 0.0
    safety_stock_reduction_percent: float = 0.0
    coefficient_of_variation_individual: float = 0.0
    coefficient_of_variation_aggregated: float = 0.0
    cv_reduction_percent: float = 0.0
    optimal_aggregation_benefit: float = 0.0

def demand_aggregation_safety_stock_reduction(input: Input) -> Output:
    """
    WHEN TO USE THIS SKILL:
    This skill evaluates the benefit of aggregating demand for generic components across multiple product configurations
    in a Push-Pull strategy. It quantifies safety stock reduction through risk pooling and decreased Coefficient of Variation (CV).
    Use this when analyzing component commonality decisions, evaluating postponement strategies, or calculating inventory
    reduction opportunities from product platforming.
    
    Inputs:
    - Input object with fields:
        - number_of_product_configurations: Number of distinct product configurations sharing the generic component (must be >= 1)
        - demand_standard_deviation_per_configuration: Standard deviation of demand for each configuration (must be > 0)
        - average_demand_per_configuration: Average demand per configuration (must be > 0)
        - target_service_level: Desired cycle service level as a decimal between 0 and 1 exclusive
    
    Returns:
    Output object containing:
    - individual_safety_stock_factor: Safety stock factor without aggregation
    - aggregated_safety_stock_factor: Safety stock factor with aggregation
    - safety_stock_reduction_percent: Percentage reduction in safety stock
    - coefficient_of_variation_individual: CV without aggregation
    - coefficient_of_variation_aggregated: CV with aggregation
    - cv_reduction_percent: Percentage reduction in CV
    - optimal_aggregation_benefit: Theoretical maximum benefit from infinite aggregation
    """
    # Input validation
    if input.number_of_product_configurations < 1:
        raise ValueError("number_of_product_configurations must be at least 1")
    if input.demand_standard_deviation_per_configuration <= 0:
        raise ValueError("demand_standard_deviation_per_configuration must be positive")
    if input.average_demand_per_configuration <= 0:
        raise ValueError("average_demand_per_configuration must be positive")
    if not (0 < input.target_service_level < 1):
        raise ValueError("target_service_level must be between 0 and 1 exclusive")
    
    n = input.number_of_product_configurations
    sigma = input.demand_standard_deviation_per_configuration
    mu = input.average_demand_per_configuration
    
    # Calculate safety stock factors (proportional to standard deviation during lead time)
    # Without aggregation: total standard deviation across all configurations
    individual_total_std = n * sigma
    # With aggregation: standard deviation of aggregate demand (assuming independence)
    aggregated_std = sigma * math.sqrt(n)
    
    # Calculate Coefficient of Variation (CV = std/mean)
    # Individual CV for each configuration
    cv_individual = sigma / mu
    # Aggregated CV: std_aggregated / mean_aggregated = (sigma*sqrt(n)) / (n*mu) = cv_individual / sqrt(n)
    cv_aggregated = cv_individual / math.sqrt(n)
    
    # Calculate reductions
    safety_stock_reduction_percent = ((individual_total_std - aggregated_std) / individual_total_std) * 100
    cv_reduction_percent = ((cv_individual - cv_aggregated) / cv_individual) * 100
    
    # Theoretical maximum benefit (as n approaches infinity)
    optimal_aggregation_benefit = (1 - (1 / math.sqrt(n))) * 100
    
    return Output(
        individual_safety_stock_factor=individual_total_std,
        aggregated_safety_stock_factor=aggregated_std,
        safety_stock_reduction_percent=safety_stock_reduction_percent,
        coefficient_of_variation_individual=cv_individual,
        coefficient_of_variation_aggregated=cv_aggregated,
        cv_reduction_percent=cv_reduction_percent,
        optimal_aggregation_benefit=optimal_aggregation_benefit
    )