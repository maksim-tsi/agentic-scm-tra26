from typing import Dict, List, Any, Union, Optional
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    component: Optional[str] = None
    gross_requirements: Optional[Dict[str, float]] = None
    parent_items: Optional[List[str]] = None
    current_demand_sources: Optional[Dict[str, Dict[str, float]]] = None


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    pegging_traces: Optional[Dict[str, Dict[str, float]]] = None
    untraced_requirements: Optional[Dict[str, float]] = None
    parent_contribution_summary: Optional[Dict[str, float]] = None
    demand_coverage_analysis: Optional[float] = None


def mrp_pegging_tracing(
    component: str,
    gross_requirements: Dict[str, float],
    parent_items: List[str],
    current_demand_sources: Dict[str, Dict[str, float]]
) -> Dict[str, Any]:
    """
    Trace a component's gross requirements back to specific parent item demands in MRP.
    
    WHEN TO USE THIS SKILL:
    This skill solves MRP pegging problems where you need to trace a component's gross requirements 
    back to specific parent item demands in material requirements planning. Use when:
    1. You need to identify which parent items are driving component demand in current production cycles
    2. You want to prioritize production or procurement based on active parent item demands
    3. You need to distinguish between current pegging (active demands) vs. static where-used analysis
    4. You require visibility into demand propagation through BOM structures for capacity planning
    5. You want to perform demand-source attribution for component shortages or expediting decisions
    
    BUSINESS CONTEXT:
    In MRP systems, pegging links component gross_requirements to specific parent item planned orders 
    or independent demands. Unlike static where-used lists that show all possible parents, pegging 
    dynamically traces only current, active demands driving production needs. This enables priority 
    control by showing exactly which parent_item items' schedules affect component availability.
    
    Args:
        component (str): Component item identifier to trace requirements for
        gross_requirements (Dict[str, float]): Total gross_requirements per period
            Format: {'period_id': quantity, ...} where period_id is time bucket identifier
        parent_items (List[str]): List of parent item identifiers that consume this component
        current_demand_sources (Dict[str, Dict[str, float]]): 
            Current demand from each parent per period
            Format: {'parent_item_id': {'period_id': quantity, ...}, ...}
    
    Returns:
        Dict[str, Any]: Dictionary containing:
            - 'pegging_traces': Dict mapping each parent to its component demand contribution per period
            - 'untraced_requirements': Dict showing any component requirements not traced to parent demands
            - 'parent_contribution_summary': Dict with total contribution by parent item
            - 'demand_coverage_analysis': Percentage of component requirements traced to parent sources
    
    Raises:
        ValueError: If component identifier is empty or None
        ValueError: If gross_requirements is empty
        ValueError: If parent_items is empty
        ValueError: If current_demand_sources is empty
        ValueError: If any demand values are negative
        ValueError: If parent items in current_demand_sources don't match parent_items list
    """
    # Input validation
    if not component or not isinstance(component, str):
        raise ValueError("Component must be a non-empty string")
    
    if not gross_requirements or not isinstance(gross_requirements, dict):
        raise ValueError("Gross requirements must be a non-empty dictionary")
    
    if not parent_items or not isinstance(parent_items, list):
        raise ValueError("Parent items must be a non-empty list")
    
    if not current_demand_sources or not isinstance(current_demand_sources, dict):
        raise ValueError("Current demand sources must be a non-empty dictionary")
    
    # Validate no negative demand values
    for period, qty in gross_requirements.items():
        if qty < 0:
            raise ValueError(f"Gross requirement for period {period} cannot be negative: {qty}")
    
    for parent, demands in current_demand_sources.items():
        for period, qty in demands.items():
            if qty < 0:
                raise ValueError(f"Demand for parent {parent} in period {period} cannot be negative: {qty}")
    
    # Validate parent items match demand sources
    demand_parents = set(current_demand_sources.keys())
    provided_parents = set(parent_items)
    
    if demand_parents != provided_parents:
        missing = provided_parents - demand_parents
        extra = demand_parents - provided_parents
        error_msg = "Parent items mismatch: "
        if missing:
            error_msg += f"Missing demand data for parents: {missing}. "
        if extra:
            error_msg += f"Unexpected parents in demand data: {extra}"
        raise ValueError(error_msg)
    
    # Initialize result structures
    all_periods = set(gross_requirements.keys())
    for demands in current_demand_sources.values():
        all_periods.update(demands.keys())
    
    pegging_traces = {}
    for parent in parent_items:
        pegging_traces[parent] = {period: Decimal('0') for period in all_periods}
    
    untraced_requirements = {period: Decimal('0') for period in all_periods}
    parent_contribution_summary = {parent: Decimal('0') for parent in parent_items}
    
    # Convert all values to Decimal for precision
    gross_req_decimal = {period: Decimal(str(qty)) for period, qty in gross_requirements.items()}
    
    # Perform pegging trace
    for period in all_periods:
        period_gross = gross_req_decimal.get(period, Decimal('0'))
        period_traced = Decimal('0')
        
        for parent in parent_items:
            parent_demand = Decimal(str(current_demand_sources[parent].get(period, 0)))
            if parent_demand > 0:
                pegging_traces[parent][period] = parent_demand
                period_traced += parent_demand
                parent_contribution_summary[parent] += parent_demand
        
        # Calculate untraced requirements for this period
        if period_gross > period_traced:
            untraced_requirements[period] = period_gross - period_traced
        else:
            untraced_requirements[period] = Decimal('0')
    
    # Calculate demand coverage analysis
    total_gross = sum(gross_req_decimal.values())
    total_traced = sum(parent_contribution_summary.values())
    
    if total_gross > 0:
        coverage_percentage = float((total_traced / total_gross) * 100)
    else:
        coverage_percentage = 0.0
    
    # Convert Decimal back to float for JSON serialization
    pegging_traces_serializable = {
        parent: {period: float(qty) for period, qty in periods.items()}
        for parent, periods in pegging_traces.items()
    }
    
    untraced_serializable = {period: float(qty) for period, qty in untraced_requirements.items()}
    
    contribution_serializable = {parent: float(qty) for parent, qty in parent_contribution_summary.items()}
    
    return {
        'pegging_traces': pegging_traces_serializable,
        'untraced_requirements': untraced_serializable,
        'parent_contribution_summary': contribution_serializable,
        'demand_coverage_analysis': coverage_percentage
    }


def run(input_data: InputSchema) -> OutputSchema:
    """Execute the MRP pegging tracing skill."""
    result = mrp_pegging_tracing(
        component=input_data.component,
        gross_requirements=input_data.gross_requirements,
        parent_items=input_data.parent_items,
        current_demand_sources=input_data.current_demand_sources
    )
    return OutputSchema(**result)