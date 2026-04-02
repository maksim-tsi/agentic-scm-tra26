from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ImpactLevel(str, Enum):
    """Enumeration for factor impact levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Likelihood(str, Enum):
    """Enumeration for factor likelihood levels."""
    UNLIKELY = "unlikely"
    POSSIBLE = "possible"
    LIKELY = "likely"
    VERY_LIKELY = "very_likely"


class MacroEnvironmentalFactor(BaseModel):
    """Represents a single macro-environmental factor for analysis."""
    model_config = ConfigDict(strict=True)

    name: str = Field(default="unnamed_factor", description="Factor identifier")
    description: str = Field(default="No description provided", description="Detailed factor description")
    impact_level: ImpactLevel = Field(default=ImpactLevel.MEDIUM, description="Impact severity level")
    likelihood: Likelihood = Field(default=Likelihood.POSSIBLE, description="Likelihood of occurrence")
    risk_score: Optional[float] = Field(default=None, description="Numeric risk score 0.0-1.0")
    opportunity_score: Optional[float] = Field(default=None, description="Numeric opportunity score 0.0-1.0")
    mitigation_strategy: Optional[str] = Field(default=None, description="Strategy to address factor")


class FactorInput(BaseModel):
    """Input structure for a single environmental factor."""
    model_config = ConfigDict(strict=True)

    name: str = Field(default="unnamed_factor")
    description: str = Field(default="No description provided")
    impact_level: str = Field(default="medium")
    likelihood: str = Field(default="possible")
    risk_score: Optional[float] = Field(default=None)
    opportunity_score: Optional[float] = Field(default=None)
    mitigation_strategy: Optional[str] = Field(default=None)


class Input(BaseModel):
    """Input schema for PESTEL macro-environment analysis."""
    model_config = ConfigDict(strict=True)

    political_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Political stability factors including government policies, trade regulations"
    )
    economic_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Economic conditions including growth rates, inflation, exchange rates"
    )
    sociocultural_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Sociocultural trends including demographics, cultural shifts"
    )
    technological_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Technological developments including innovation rates, automation"
    )
    environmental_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Environmental policies including sustainability, climate regulations"
    )
    legal_factors: List[FactorInput] = Field(
        default_factory=list,
        description="Legal and regulatory requirements including employment laws, compliance"
    )


class Output(BaseModel):
    """Output schema for PESTEL macro-environment analysis."""
    model_config = ConfigDict(strict=True)

    political_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    economic_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    sociocultural_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    technological_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    environmental_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    legal_factors: List[MacroEnvironmentalFactor] = Field(default_factory=list)
    overall_risk_rating: Optional[str] = Field(default=None, description="Overall risk: low/moderate/high/critical")
    total_factors_analyzed: int = Field(default=0, description="Total number of factors analyzed")
    high_impact_count: int = Field(default=0, description="Count of high/critical impact factors")
    strategic_recommendations: List[str] = Field(default_factory=list, description="Strategic action items")


def _validate_factor_input(factor: FactorInput, index: int, category: str) -> None:
    """Validate a single factor input."""
    if not factor.name or not factor.name.strip():
        raise ValueError(f"{category} factor at index {index}: name cannot be empty")
    if not factor.description or not factor.description.strip():
        raise ValueError(f"{category} factor at index {index}: description cannot be empty")
    
    valid_impacts = [e.value for e in ImpactLevel]
    if factor.impact_level.lower().strip() not in valid_impacts:
        raise ValueError(f"{category} factor at index {index}: invalid impact_level '{factor.impact_level}'. Must be one of {valid_impacts}")
    
    valid_likelihoods = [e.value for e in Likelihood]
    if factor.likelihood.lower().strip() not in valid_likelihoods:
        raise ValueError(f"{category} factor at index {index}: invalid likelihood '{factor.likelihood}'. Must be one of {valid_likelihoods}")
    
    if factor.risk_score is not None:
        if not isinstance(factor.risk_score, (int, float)):
            raise ValueError(f"{category} factor at index {index}: risk_score must be numeric")
        if factor.risk_score < 0.0 or factor.risk_score > 1.0:
            raise ValueError(f"{category} factor at index {index}: risk_score must be between 0.0 and 1.0")
    
    if factor.opportunity_score is not None:
        if not isinstance(factor.opportunity_score, (int, float)):
            raise ValueError(f"{category} factor at index {index}: opportunity_score must be numeric")
        if factor.opportunity_score < 0.0 or factor.opportunity_score > 1.0:
            raise ValueError(f"{category} factor at index {index}: opportunity_score must be between 0.0 and 1.0")


def _convert_factor(factor_input: FactorInput) -> MacroEnvironmentalFactor:
    """Convert FactorInput to MacroEnvironmentalFactor."""
    return MacroEnvironmentalFactor(
        name=factor_input.name.strip(),
        description=factor_input.description.strip(),
        impact_level=ImpactLevel(factor_input.impact_level.lower().strip()),
        likelihood=Likelihood(factor_input.likelihood.lower().strip()),
        risk_score=factor_input.risk_score,
        opportunity_score=factor_input.opportunity_score,
        mitigation_strategy=factor_input.mitigation_strategy
    )


def perform_pestel_analysis(input_data: Input) -> Output:
    """Perform comprehensive PESTEL macro-environment analysis.

    WHEN TO USE THIS SKILL:
    Use this skill when you need to systematically scan and assess the external
    macro environment for non-market factors that impact business profitability,
    project viability, and risk profiles. This tool is ideal for:

    - Strategic planning and market entry decisions requiring environmental scanning
    - Project risk assessment and due diligence with external factor analysis
    - Business case development and feasibility studies considering macro trends
    - Competitive environment scanning across political, economic, social dimensions
    - Regulatory compliance assessment and legal risk identification
    - Supply chain risk management considering geopolitical and environmental factors
    - Investment analysis requiring PESTEL framework categorization
    - Corporate strategy sessions evaluating external opportunities and threats

    The PESTEL framework systematically categorizes factors into:
    - Political: Government stability, trade policies, tax policies, political risk
    - Economic: Economic growth, inflation, exchange rates, labor costs, market conditions
    - Sociocultural: Demographics, cultural trends, education levels, consumer behavior
    - Technological: Innovation rates, automation, R&D activity, digital transformation
    - Environmental: Climate change, sustainability regulations, resource scarcity
    - Legal: Employment laws, health & safety, consumer protection, compliance requirements

    Inputs:
        input_data: Input model containing six categories of environmental factors.
            Each category accepts a list of FactorInput objects with:
            - name (str): Factor identifier
            - description (str): Detailed factor description
            - impact_level (str): One of "low", "medium", "high", "critical"
            - likelihood (str): One of "unlikely", "possible", "likely", "very_likely"
            - risk_score (Optional[float]): Numeric risk score 0.0-1.0
            - opportunity_score (Optional[float]): Numeric opportunity score 0.0-1.0
            - mitigation_strategy (Optional[str]): Strategy to address factor

    Output:
        Output model containing:
        - Categorized factors across all six PESTEL dimensions
        - overall_risk_rating: Aggregated risk assessment (low/moderate/high/critical)
        - total_factors_analyzed: Count of all factors processed
        - high_impact_count: Count of high/critical impact factors
        - strategic_recommendations: Actionable strategic guidance

    Raises:
        ValueError: If any factor has invalid impact_level or likelihood values
        ValueError: If risk_score or opportunity_score are outside [0.0, 1.0]
        ValueError: If factor name or description is empty
    """
    # Defensive validation: Check all factor inputs
    categories = [
        (input_data.political_factors, "political_factors"),
        (input_data.economic_factors, "economic_factors"),
        (input_data.sociocultural_factors, "sociocultural_factors"),
        (input_data.technological_factors, "technological_factors"),
        (input_data.environmental_factors, "environmental_factors"),
        (input_data.legal_factors, "legal_factors")
    ]

    for factor_list, category_name in categories:
        for idx, factor in enumerate(factor_list):
            _validate_factor_input(factor, idx, category_name)

    # Convert all inputs to output format
    political = [_convert_factor(f) for f in input_data.political_factors]
    economic = [_convert_factor(f) for f in input_data.economic_factors]
    sociocultural = [_convert_factor(f) for f in input_data.sociocultural_factors]
    technological = [_convert_factor(f) for f in input_data.technological_factors]
    environmental = [_convert_factor(f) for f in input_data.environmental_factors]
    legal = [_convert_factor(f) for f in input_data.legal_factors]

    all_factors = political + economic + sociocultural + technological + environmental + legal

    # Calculate risk metrics
    overall_risk_rating = None
    high_impact_count = 0

    if all_factors:
        impact_scores = {
            ImpactLevel.LOW: 1,
            ImpactLevel.MEDIUM: 2,
            ImpactLevel.HIGH: 3,
            ImpactLevel.CRITICAL: 4
        }
        likelihood_scores = {
            Likelihood.UNLIKELY: 1,
            Likelihood.POSSIBLE: 2,
            Likelihood.LIKELY: 3,
            Likelihood.VERY_LIKELY: 4
        }

        total_score = sum(
            impact_scores[f.impact_level] * likelihood_scores[f.likelihood]
            for f in all_factors
        )
        max_possible = 4 * 4 * len(all_factors)
        risk_percentage = (total_score / max_possible) * 100 if max_possible > 0 else 0

        if risk_percentage < 25:
            overall_risk_rating = "low"
        elif risk_percentage < 50:
            overall_risk_rating = "moderate"
        elif risk_percentage < 75:
            overall_risk_rating = "high"
        else:
            overall_risk_rating = "critical"

        high_impact_count = sum(
            1 for f in all_factors
            if f.impact_level in [ImpactLevel.HIGH, ImpactLevel.CRITICAL]
        )

    # Generate strategic recommendations
    recommendations = []
    if high_impact_count > 0:
        recommendations.append(f"Monitor {high_impact_count} high/critical impact factors closely for risk mitigation")
    if economic:
        recommendations.append("Conduct regular economic indicator monitoring for market timing decisions")
    if legal or environmental:
        recommendations.append("Establish regulatory compliance tracking system for legal and environmental factors")
    if technological:
        recommendations.append("Assess technology adoption readiness and digital transformation opportunities")
    if political:
        recommendations.append("Develop geopolitical risk contingency plans for political stability factors")
    if sociocultural:
        recommendations.append("Monitor sociocultural trends for consumer behavior and market demand shifts")

    return Output(
        political_factors=political,
        economic_factors=economic,
        sociocultural_factors=sociocultural,
        technological_factors=technological,
        environmental_factors=environmental,
        legal_factors=legal,
        overall_risk_rating=overall_risk_rating,
        total_factors_analyzed=len(all_factors),
        high_impact_count=high_impact_count,
        strategic_recommendations=recommendations
    )