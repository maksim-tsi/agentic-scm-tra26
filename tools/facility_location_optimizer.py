import pulp
from pydantic import BaseModel, ConfigDict

class InputSchema(BaseModel):
    fixed_costs: list[float] = []
    capacities: list[float] = []
    demands: list[float] = []
    shipping_costs: list[list[float]] = []

    model_config = ConfigDict(strict=True)

class OutputSchema(BaseModel):
    status: str = ""
    open_plants: list[int] = []
    shipment_quantities: list[list[float]] = []
    total_cost: float = 0.0

    model_config = ConfigDict(strict=True)

def optimize_facility_location(input_data: InputSchema) -> OutputSchema:
    """
    Solve a facility location and capacity planning problem to minimize total network costs.

    WHEN TO USE THIS SKILL:
    Use this skill for supply chain network design decisions where you need to determine the optimal number, location, and capacity of production facilities. It addresses problems such as:
    - Opening or closing plants to reduce fixed and variable costs.
    - Allocating production and shipping quantities to meet market demands efficiently.
    - Balancing capacity constraints with demand fulfillment in a global supply chain.
    - Minimizing total costs including fixed facility costs and variable production/shipping costs.
    This is applicable in strategic planning, capacity expansion, and cost optimization scenarios in manufacturing and logistics.

    Inputs:
    - input_data (InputSchema): Contains fixed_costs, capacities, demands, and shipping_costs.

    Output:
    OutputSchema: A Pydantic model containing status, open_plants, shipment_quantities, and total_cost.
    """
    # Extract data from input
    fixed_costs = input_data.fixed_costs
    capacities = input_data.capacities
    demands = input_data.demands
    shipping_costs = input_data.shipping_costs

    # Input validation
    if not fixed_costs or not capacities or not demands or not shipping_costs:
        raise ValueError("All input lists must be non-empty.")
    
    num_plants = len(fixed_costs)
    num_markets = len(demands)
    
    if len(capacities) != num_plants:
        raise ValueError("Length of capacities must match length of fixed_costs (number of plants).")
    
    if len(shipping_costs) != num_plants:
        raise ValueError("Number of rows in shipping_costs must match number of plants.")
    for i in range(num_plants):
        if len(shipping_costs[i]) != num_markets:
            raise ValueError(f"Row {i} of shipping_costs must have {num_markets} elements (number of markets).")
    
    for cost in fixed_costs:
        if cost < 0:
            raise ValueError("Fixed costs must be non-negative.")
    for cap in capacities:
        if cap < 0:
            raise ValueError("Capacities must be non-negative.")
    for dem in demands:
        if dem < 0:
            raise ValueError("Demands must be non-negative.")
    for i in range(num_plants):
        for j in range(num_markets):
            if shipping_costs[i][j] < 0:
                raise ValueError("Shipping costs must be non-negative.")
    
    # Initialize the MIP problem
    prob = pulp.LpProblem("Facility_Location_Capacity_Planning", pulp.LpMinimize)
    
    # Decision variables
    plant_open = [pulp.LpVariable(f"plant_open_{i}", cat='Binary') for i in range(num_plants)]
    shipment = [[pulp.LpVariable(f"shipment_{i}_{j}", lowBound=0, cat='Continuous') for j in range(num_markets)] for i in range(num_plants)]
    
    # Objective function: minimize total cost
    total_fixed_cost = pulp.lpSum(fixed_costs[i] * plant_open[i] for i in range(num_plants))
    total_shipping_cost = pulp.lpSum(shipping_costs[i][j] * shipment[i][j] for i in range(num_plants) for j in range(num_markets))
    prob += total_fixed_cost + total_shipping_cost, "Total_Cost"
    
    # Constraints
    # Demand fulfillment: for each market, sum of shipments equals demand
    for j in range(num_markets):
        prob += pulp.lpSum(shipment[i][j] for i in range(num_plants)) == demands[j], f"Demand_Constraint_Market_{j}"
    
    # Capacity constraint: for each plant, sum of shipments does not exceed capacity if plant is open
    for i in range(num_plants):
        prob += pulp.lpSum(shipment[i][j] for j in range(num_markets)) <= capacities[i] * plant_open[i], f"Capacity_Constraint_Plant_{i}"
    
    # Solve the problem
    prob.solve(pulp.PULP_CBC_CMD(msg=False))  # Suppress solver output for cleanliness
    
    # Extract results
    status = pulp.LpStatus[prob.status]
    open_plants = [int(plant_open[i].varValue) for i in range(num_plants)]
    shipment_quantities = [[shipment[i][j].varValue for j in range(num_markets)] for i in range(num_plants)]
    total_cost = pulp.value(prob.objective)
    
    # Return as OutputSchema
    return OutputSchema(
        status=status,
        open_plants=open_plants,
        shipment_quantities=shipment_quantities,
        total_cost=total_cost
    )