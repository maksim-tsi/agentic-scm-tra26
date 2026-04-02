from pydantic import BaseModel, ConfigDict, field_validator
from typing import List


class Order(BaseModel):
    model_config = ConfigDict(strict=True)

    planned_order_release_quantity: float = 0.0
    setup_time_standard_hours: float = 0.0
    run_time_per_unit_standard_hours: float = 0.0

    @field_validator('planned_order_release_quantity', 'setup_time_standard_hours', 'run_time_per_unit_standard_hours')
    @classmethod
    def check_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class Input(BaseModel):
    model_config = ConfigDict(strict=True)

    planned_order_releases: List[Order] = []


class Output(BaseModel):
    model_config = ConfigDict(strict=True)

    total_load: float = 0.0


def calculate_work_center_load(input_data: Input) -> Output:
    """
    Calculate the total load on a work center from a planned order release schedule.

    WHEN TO USE THIS SKILL:
    This skill is used in capacity planning to compute the total workload (in standard hours) on a work center for a given time period. It combines setup times and run times from multiple planned orders to help in scheduling, identifying bottlenecks, and making capacity adjustment decisions. Typical business problems include evaluating work center utilization, planning production schedules, and assessing capacity requirements.

    Inputs:
        input_data (Input): A Pydantic model containing a list of planned orders, where each order has:
            - planned_order_release_quantity (float): The quantity of units to be produced. Must be non-negative.
            - setup_time_standard_hours (float): The setup time required for the order in standard hours. Must be non-negative.
            - run_time_per_unit_standard_hours (float): The run time per unit in standard hours. Must be non-negative.

    Output:
        Output: A Pydantic model with the total load in standard hours.
    """
    # Explicit input validation
    if not input_data.planned_order_releases:
        raise ValueError("planned_order_releases cannot be empty")

    total_load = 0.0
    for order in input_data.planned_order_releases:
        # Pydantic already validates non-negativity via field validators
        load_per_order = order.setup_time_standard_hours + (order.planned_order_release_quantity * order.run_time_per_unit_standard_hours)
        total_load += load_per_order

    return Output(total_load=total_load)