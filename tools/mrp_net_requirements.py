from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    gross_requirements: float = 0.0
    scheduled_receipts: float = 0.0
    projected_available_balance_prior_period: float = 0.0

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    net_requirements: float = 0.0

def calculate_net_requirements(input: Input) -> Output:
    """
    Calculate Net Requirements for a Material Requirements Planning (MRP) system period.
    
    WHEN TO USE THIS SKILL:
    Use this skill when determining the net material requirement for a specific planning period in an MRP system.
    It solves the fundamental MRP calculation of how much additional material must be procured or produced
    after accounting for existing inventory and incoming shipments. Essential for:
    - Master Production Schedule (MPS) explosion
    - Procurement planning and purchase order generation
    - Production order scheduling
    - Inventory policy implementation (safety stock, lot sizing decisions)
    - Supply chain coordination across planning horizons
    
    The calculation subtracts scheduled receipts and projected available inventory from gross requirements
    to determine actual material needs, which drives downstream procurement and production activities.
    
    Args:
        input (Input): Pydantic model containing:
            gross_requirements (float): Total demand for the item in the planning period (units). Must be non-negative.
            scheduled_receipts (float): Open purchase orders or production orders scheduled to arrive in the planning period (units). Must be non-negative.
            projected_available_balance_prior_period (float): Expected inventory on hand at the start of the planning period (units). Must be non-negative.
    
    Returns:
        Output: Pydantic model with field:
            net_requirements (float): Net requirements for the planning period (units). Returns 0.0 if calculation yields negative result (excess inventory).
    
    Raises:
        ValueError: If any input parameter is negative or non-numeric. Since Pydantic ensures type, this checks value ranges.
    """
    # Input validation - defensive programming
    if input.gross_requirements < 0:
        raise ValueError("gross_requirements cannot be negative")
    if input.scheduled_receipts < 0:
        raise ValueError("scheduled_receipts cannot be negative")
    if input.projected_available_balance_prior_period < 0:
        raise ValueError("projected_available_balance_prior_period cannot be negative")
    
    # Core MRP net requirements calculation
    # Net Requirements = Gross Requirements - Scheduled Receipts - Projected Available Balance
    raw_net_requirements = input.gross_requirements - input.scheduled_receipts - input.projected_available_balance_prior_period
    
    # In MRP systems, negative net requirements indicate excess inventory
    # Standard practice: net requirements cannot be negative (minimum of 0)
    net_requirements = max(0.0, raw_net_requirements)
    
    return Output(net_requirements=net_requirements)