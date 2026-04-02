from typing import Optional
from pydantic import BaseModel, ConfigDict

class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    product_architecture: Optional[str] = None
    system_dependencies: Optional[str] = None
    internal_manufacturing_capacity: Optional[bool] = None
    internal_knowledge_level: Optional[str] = None
    external_knowledge_level: Optional[str] = None

class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    recommendation: Optional[str] = None

def make_buy_decision(input_data: InputSchema) -> OutputSchema:
    """
    Recommend make or buy decision for a modular component based on system dependencies and knowledge levels.

    WHEN TO USE THIS SKILL:
    This skill is used for strategic make/buy decisions involving modular products with low system dependencies, where internal manufacturing capacity exists but external knowledge is superior. It helps prioritize knowledge capture and control over production capacity, guiding whether to manufacture in-house or outsource to specialists while retaining design expertise.

    Inputs:
    - InputSchema with fields: product_architecture, system_dependencies, internal_manufacturing_capacity, internal_knowledge_level, external_knowledge_level.

    Output:
    - OutputSchema with field recommendation: str, either "make" or "buy".
    """
    # Input validation
    if input_data.product_architecture is None:
        raise ValueError("product_architecture is required")
    if input_data.system_dependencies is None:
        raise ValueError("system_dependencies is required")
    if input_data.internal_manufacturing_capacity is None:
        raise ValueError("internal_manufacturing_capacity is required")
    if input_data.internal_knowledge_level is None:
        raise ValueError("internal_knowledge_level is required")
    if input_data.external_knowledge_level is None:
        raise ValueError("external_knowledge_level is required")

    valid_architectures = ["modular", "integral"]
    valid_dependencies = ["low", "high"]
    valid_knowledge_levels = ["low", "medium", "high"]

    if input_data.product_architecture not in valid_architectures:
        raise ValueError(f"product_architecture must be one of {valid_architectures}")
    if input_data.system_dependencies not in valid_dependencies:
        raise ValueError(f"system_dependencies must be one of {valid_dependencies}")
    if not isinstance(input_data.internal_manufacturing_capacity, bool):
        raise ValueError("internal_manufacturing_capacity must be a boolean")
    if input_data.internal_knowledge_level not in valid_knowledge_levels:
        raise ValueError(f"internal_knowledge_level must be one of {valid_knowledge_levels}")
    if input_data.external_knowledge_level not in valid_knowledge_levels:
        raise ValueError(f"external_knowledge_level must be one of {valid_knowledge_levels}")

    # Decision logic based on qualitative framework
    if input_data.product_architecture == "modular" and input_data.system_dependencies == "low":
        # Prioritize knowledge capture over internal capacity
        if input_data.external_knowledge_level == "high" and input_data.internal_knowledge_level != "high":
            # External knowledge is superior; outsource manufacturing while retaining knowledge control
            recommendation = "buy"
        else:
            # Internal knowledge is adequate or superior; prefer in-house manufacturing
            recommendation = "make"
    else:
        # For non-modular or high dependencies, default to capacity-based decision
        if input_data.internal_manufacturing_capacity:
            recommendation = "make"
        else:
            recommendation = "buy"

    return OutputSchema(recommendation=recommendation)