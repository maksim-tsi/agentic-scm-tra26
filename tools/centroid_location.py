from typing import List, Tuple
from pydantic import BaseModel, ConfigDict


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    x_coords: List[float] = []
    y_coords: List[float] = []


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    optimal_x_coord: float = 0.0
    optimal_y_coord: float = 0.0


def calculate_optimal_facility_coordinates(x_coords: List[float], y_coords: List[float]) -> Tuple[float, float]:
    """
    Calculate the geographic coordinates for a single new facility to minimize the average straight-line distance
    to a set of existing facilities, assuming equal demand/volume across all locations.
    
    WHEN TO USE THIS SKILL:
    This skill should be used for facility location problems in supply chain network design where:
    1. You need to determine optimal coordinates for a new facility (warehouse, distribution center, etc.)
    2. Demand is assumed to be equal across all existing locations
    3. The objective is to minimize average transportation distance
    4. You're using a centroid-based location model with equal weights
    5. You need to solve uncapacitated facility location problems with uniform demand
    
    Inputs:
        x_coords: List[float] - X-coordinates of existing facilities (must be non-empty)
        y_coords: List[float] - Y-coordinates of existing facilities (must match x_coords length)
    
    Outputs:
        Tuple[float, float] - Optimal (x_coord, y_coord) for new facility
    
    Raises:
        ValueError: If input lists are empty, have different lengths, or contain invalid values
    """
    # Defensive programming: Input validation
    if not x_coords or not y_coords:
        raise ValueError("Input coordinate lists must not be empty")
    
    if len(x_coords) != len(y_coords):
        raise ValueError("x_coords and y_coords must have the same length")
    
    if len(x_coords) == 0:
        raise ValueError("At least one facility coordinate pair is required")
    
    # Validate all coordinates are numeric
    for i, (x, y) in enumerate(zip(x_coords, y_coords)):
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"All coordinates must be numeric, found non-numeric at index {i}")
        
        if x is None or y is None:
            raise ValueError(f"Coordinates cannot be None, found None at index {i}")
    
    # Calculate optimal coordinates using centroid method (equal weights)
    number_of_facilities = len(x_coords)
    
    # Guard against division by zero (already checked above, but defensive)
    if number_of_facilities == 0:
        raise ValueError("Cannot calculate centroid with zero facilities")
    
    optimal_x_coord = sum(x_coords) / number_of_facilities
    optimal_y_coord = sum(y_coords) / number_of_facilities
    
    return optimal_x_coord, optimal_y_coord


def main(input_data: InputSchema) -> OutputSchema:
    """
    Main entry point for the facility location optimization skill.
    
    Args:
        input_data: InputSchema containing x_coords and y_coords lists
        
    Returns:
        OutputSchema with optimal_x_coord and optimal_y_coord
    """
    # Extract coordinates from input schema
    x_coords = input_data.x_coords
    y_coords = input_data.y_coords
    
    # Calculate optimal coordinates
    optimal_x, optimal_y = calculate_optimal_facility_coordinates(x_coords, y_coords)
    
    # Return as OutputSchema
    return OutputSchema(
        optimal_x_coord=optimal_x,
        optimal_y_coord=optimal_y
    )