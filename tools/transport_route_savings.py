from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    cost_per_distance_unit: float = 0.0
    dist_importer_to_terminal: float = 0.0
    dist_terminal_to_exporter: float = 0.0
    dist_importer_to_exporter: float = 0.0

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    net_savings: float = 0.0

def calculate_direct_rotation_cost_savings(input_obj: Input) -> Output:
    """
    Calculate the net transportation cost savings achieved by synchronizing import and export flows
    through direct rotation instead of routing back through a terminal.

    WHEN TO USE THIS SKILL:
    This skill is used in logistics and supply chain management to evaluate the cost benefits of
    optimizing transportation routes. Specifically, it helps in deciding whether to use a direct
    rotation between importer and exporter locations versus the standard routing that goes through
    a central terminal. It is applicable in scenarios such as freight consolidation, port operations,
    and intermodal transport planning where reducing empty miles and improving asset utilization are key.

    Inputs:
    - input_obj (Input): An Input object containing cost_per_distance_unit, dist_importer_to_terminal,
      dist_terminal_to_exporter, and dist_importer_to_exporter as floats.

    Output:
    - Output: An Output object with net_savings as the net cost savings from using direct rotation over standard routing.

    Raises:
    - ValueError: If any input is not a number, if cost_per_distance_unit is not positive,
      if any distance is negative, or if direct rotation cost is not less than standard routing cost.
    """
    # Input validation
    if not all(isinstance(param, (int, float)) for param in [input_obj.cost_per_distance_unit, input_obj.dist_importer_to_terminal, input_obj.dist_terminal_to_exporter, input_obj.dist_importer_to_exporter]):
        raise ValueError("All inputs must be numeric.")
    if input_obj.cost_per_distance_unit <= 0:
        raise ValueError("cost_per_distance_unit must be positive.")
    if input_obj.dist_importer_to_terminal < 0 or input_obj.dist_terminal_to_exporter < 0 or input_obj.dist_importer_to_exporter < 0:
        raise ValueError("Distances must be non-negative.")
    
    # Calculate costs
    standard_routing_cost = input_obj.cost_per_distance_unit * (input_obj.dist_importer_to_terminal + input_obj.dist_terminal_to_exporter)
    direct_rotation_cost = input_obj.cost_per_distance_unit * input_obj.dist_importer_to_exporter
    
    # Check constraint
    if direct_rotation_cost >= standard_routing_cost:
        raise ValueError("Direct rotation cost must be less than standard routing cost for savings to be positive.")
    
    # Calculate net savings
    net_savings = standard_routing_cost - direct_rotation_cost
    
    return Output(net_savings=net_savings)