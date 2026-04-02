from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    """Input schema for terminal truck capacity calculation."""
    model_config = ConfigDict(strict=True)
    number_of_equipment_units: float = 1.0
    equipment_move_rate: float = 1.0
    moves_per_truck: float = 1.0


class Output(BaseModel):
    """Output schema for terminal truck capacity calculation."""
    model_config = ConfigDict(strict=True)
    max_trucks_serviced_per_hour: float = 0.0


def calculate_terminal_truck_capacity(input: Input) -> Output:
    """
    Calculate the maximum number of landside trucks that can be serviced at a container
    terminal per hour based on yard equipment capacity and required moves per truck.

    WHEN TO USE THIS SKILL:
    Use this skill for terminal capacity planning, equipment allocation optimization,
    and truck turnaround time analysis. It solves problems related to determining
    maximum throughput for landside operations, evaluating equipment utilization,
    and identifying bottlenecks in container handling processes. Apply when planning
    yard expansions, optimizing resource allocation, or establishing service level
    agreements for truck processing times.

    Inputs:
        input (Input): Contains number_of_equipment_units (count of yard equipment),
                       equipment_move_rate (moves per unit per hour),
                       and moves_per_truck (required moves per truck).

    Returns:
        Output: Contains max_trucks_serviced_per_hour (maximum truck throughput).

    Raises:
        ValueError: If any input parameter is invalid (negative or zero where not allowed).
    """
    # Defensive input validation
    if input.number_of_equipment_units <= 0:
        raise ValueError("number_of_equipment_units must be positive.")
    if input.equipment_move_rate <= 0:
        raise ValueError("equipment_move_rate must be positive.")
    if input.moves_per_truck <= 0:
        raise ValueError("moves_per_truck must be positive to avoid division by zero.")

    # Core calculation using provided formula
    max_trucks = (input.number_of_equipment_units * input.equipment_move_rate) / input.moves_per_truck

    return Output(max_trucks_serviced_per_hour=max_trucks)