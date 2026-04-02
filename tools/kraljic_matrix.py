from pydantic import BaseModel, ConfigDict
from typing import Optional

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    profit_impact: Optional[str] = None
    supply_risk: Optional[str] = None

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    item_classification: Optional[str] = None
    procurement_strategy: Optional[str] = None
    profit_impact: Optional[str] = None
    supply_risk: Optional[str] = None

def kraljic_supply_matrix_classification(input_data: Input) -> Output:
    """
    Classify supply items in the Kraljic Supply Matrix to identify Strategic Items
    based on high Profit Impact and high Supply Risk, and determine the primary
    procurement strategy.

    WHEN TO USE THIS SKILL:
    Use this skill when you need to:
    - Classify a supply item or material into one of the four Kraljic Matrix quadrants
      (Strategic, Leverage, Bottleneck, Non-Critical) based on its profit impact and
      supply risk characteristics.
    - Determine the appropriate procurement strategy for a given supply item.
    - Prioritize supplier management efforts across a portfolio of purchased items.
    - Decide whether to pursue long-term partnerships, competitive bidding, supply
      assurance tactics, or simplified procurement processes.
    - Support strategic sourcing decisions in supply chain management.

    Inputs:
        input_data (Input): A Pydantic model containing:
            - profit_impact (str): The profit impact level, must be "high" or "low".
            - supply_risk (str): The supply risk level, must be "high" or "low".

    Output:
        Output: A Pydantic model containing:
            - item_classification (str): The Kraljic Matrix quadrant classification.
            - procurement_strategy (str): The recommended procurement strategy.
            - profit_impact (str): Normalized profit impact value.
            - supply_risk (str): Normalized supply risk value.

    Raises:
        ValueError: If profit_impact or supply_risk is not provided or invalid.
    """
    # Defensive programming: validate inputs
    profit_impact = input_data.profit_impact
    supply_risk = input_data.supply_risk
    
    if profit_impact is None:
        raise ValueError("profit_impact must be provided")
    if supply_risk is None:
        raise ValueError("supply_risk must be provided")
    
    valid_levels = {"high", "low"}
    
    if not isinstance(profit_impact, str):
        raise ValueError(f"profit_impact must be a string, got {type(profit_impact).__name__}")
    if not isinstance(supply_risk, str):
        raise ValueError(f"supply_risk must be a string, got {type(supply_risk).__name__}")
    
    profit_impact_normalized = profit_impact.strip().lower()
    supply_risk_normalized = supply_risk.strip().lower()
    
    if profit_impact_normalized not in valid_levels:
        raise ValueError(f"profit_impact must be 'high' or 'low', got '{profit_impact}'")
    if supply_risk_normalized not in valid_levels:
        raise ValueError(f"supply_risk must be 'high' or 'low', got '{supply_risk}'")
    
    # Kraljic Matrix classification logic
    if profit_impact_normalized == "high" and supply_risk_normalized == "high":
        item_classification = "strategic"
        procurement_strategy = (
            "Risk mitigation through long-term partnerships. "
            "Focus on supply assurance, joint ventures, and collaborative "
            "relationships with key suppliers. Shift from cost focus to "
            "partnership-based supply security."
        )
    elif profit_impact_normalized == "high" and supply_risk_normalized == "low":
        item_classification = "leverage"
        procurement_strategy = (
            "Competitive bidding and market-based purchasing. "
            "Leverage buying power to obtain best prices through "
            "tenders, e-auctions, and volume consolidation."
        )
    elif profit_impact_normalized == "low" and supply_risk_normalized == "high":
        item_classification = "bottleneck"
        procurement_strategy = (
            "Ensure supply continuity through multiple sources. "
            "Secure long-term contracts, develop alternative suppliers, "
            "and maintain buffer stocks to mitigate availability risks."
        )
    else:
        # profit_impact == "low" and supply_risk == "low"
        item_classification = "non_critical"
        procurement_strategy = (
            "Simplify procurement processes and reduce costs. "
            "Use catalog ordering, electronic procurement, and "
            "administrative automation to minimize transaction costs."
        )
    
    return Output(
        item_classification=item_classification,
        procurement_strategy=procurement_strategy,
        profit_impact=profit_impact_normalized,
        supply_risk=supply_risk_normalized,
    )