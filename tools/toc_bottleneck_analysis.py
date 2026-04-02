from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class ResourceModel(BaseModel):
    model_config = ConfigDict(strict=True)
    resource_id: str = "default_resource"
    constraint_capacity: float = 1.0
    lead_time: float = 0.0
    current_utilization: float = 0.5


class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    resources: List[ResourceModel] = []
    unit_purchase_cost: float = 1.0
    selling_price: float = 2.0
    lead_times: Optional[List[float]] = None


class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    system_throughput: float = 0.0
    bottleneck_utilization: float = 0.0
    constraint_capacity: float = 0.0
    lead_times: Optional[List[float]] = None
    profit: float = 0.0
    bottleneck_resource_id: str = ""
    recommendations: List[str] = []


def analyze_toc_scheduling(input_data: Input) -> Output:
    """Comprehensive TOC scheduling analysis for bottleneck management.

    WHEN TO USE THIS SKILL:
    - When you need to identify the bottleneck resource in a production or service system to maximize system throughput and profit.
    - For scheduling optimization where system performance is constrained by a specific resource.
    - In capacity planning to determine which resource elevations will increase overall throughput.
    - For profit optimization through bottleneck management, contrasting with traditional utilization maximization.
    - When analyzing lead times and their impact on system performance in constrained environments.
    - When applying Theory of Constraints (TOC) drum-buffer-rope scheduling methodology.

    Args:
        input_data: Input object containing resources with constraint capacities, utilization levels,
            unit purchase cost, selling price, and optional lead times.

    Returns:
        Output object with system_throughput, bottleneck_utilization, constraint_capacity,
            lead_times, profit, bottleneck_resource_id, and actionable recommendations.

    Raises:
        ValueError: If resources list is empty, costs are non-positive, selling_price does not
            exceed unit_purchase_cost, or any resource has invalid constraint_capacity (non-positive),
            negative lead_time, or current_utilization outside [0.0, 1.0].
    """
    # Defensive programming: input validation
    if not input_data.resources:
        raise ValueError("resources list cannot be empty; at least one resource is required")

    if input_data.unit_purchase_cost <= 0:
        raise ValueError("unit_purchase_cost must be positive")

    if input_data.selling_price <= 0:
        raise ValueError("selling_price must be positive")

    if input_data.selling_price <= input_data.unit_purchase_cost:
        raise ValueError(
            "selling_price must exceed unit_purchase_cost for positive throughput margin"
        )

    # Validate each resource
    for resource in input_data.resources:
        if resource.constraint_capacity <= 0:
            raise ValueError(
                f"Resource '{resource.resource_id}' has invalid constraint_capacity: "
                f"{resource.constraint_capacity}. Must be positive."
            )
        if resource.lead_time < 0:
            raise ValueError(
                f"Resource '{resource.resource_id}' has invalid lead_time: "
                f"{resource.lead_time}. Must be non-negative."
            )
        if not (0.0 <= resource.current_utilization <= 1.0):
            raise ValueError(
                f"Resource '{resource.resource_id}' has invalid current_utilization: "
                f"{resource.current_utilization}. Must be between 0.0 and 1.0."
            )

    # Identify bottleneck: resource with lowest constraint_capacity
    bottleneck = min(input_data.resources, key=lambda r: r.constraint_capacity)

    # Calculate system throughput governed by bottleneck
    system_throughput = bottleneck.constraint_capacity * bottleneck.current_utilization

    # Calculate profit based on throughput margin
    margin_per_unit = input_data.selling_price - input_data.unit_purchase_cost
    profit = system_throughput * margin_per_unit

    # Generate actionable TOC recommendations
    recommendations: List[str] = []

    if bottleneck.current_utilization < 0.95:
        recommendations.append(
            f"Elevate bottleneck '{bottleneck.resource_id}' utilization from "
            f"{bottleneck.current_utilization:.1%} toward 100% to maximize throughput"
        )

    for resource in input_data.resources:
        if (
            resource.resource_id != bottleneck.resource_id
            and resource.current_utilization > 0.8
        ):
            recommendations.append(
                f"Consider reducing focus on non-bottleneck '{resource.resource_id}' "
                f"(utilization {resource.current_utilization:.1%}) - TOC prioritizes bottleneck throughput"
            )

    if not recommendations:
        recommendations.append(
            "Bottleneck utilization is near capacity; consider investing in constraint elevation"
        )

    # Handle lead_times propagation
    output_lead_times: Optional[List[float]] = input_data.lead_times

    return Output(
        system_throughput=system_throughput,
        bottleneck_utilization=bottleneck.current_utilization,
        constraint_capacity=bottleneck.constraint_capacity,
        lead_times=output_lead_times,
        profit=profit,
        bottleneck_resource_id=bottleneck.resource_id,
        recommendations=recommendations,
    )
