from typing import List
from pydantic import BaseModel, ConfigDict

class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    cause_frequencies: List[float] = []
    target_cumulative_percentage: float = 80.0

class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    vital_causes_indices: List[int] = []

def apply_pareto_principle(input: InputSchema) -> OutputSchema:
    """
    WHEN TO USE THIS SKILL:
    This skill is used in quality management and continuous improvement to apply the Pareto Principle.
    It helps identify the vital few causes that contribute most significantly to total occurrences,
    allowing teams to focus resources on high-impact areas. Common in root cause analysis,
    defect reduction, and process improvement initiatives where prioritizing issues is critical.
    
    Inputs:
    - cause_frequencies: A list of non-negative numbers representing the frequency or count of each cause.
    - target_cumulative_percentage: The target cumulative percentage (between 0 and 100) to achieve.
    
    Output:
    - A list of indices (0-based) of the vital few causes that cumulatively account for at least
      the target percentage of total occurrences, sorted by frequency descending.
    """
    # Input validation
    cause_frequencies = input.cause_frequencies
    target_cumulative_percentage = input.target_cumulative_percentage
    
    if not cause_frequencies:
        raise ValueError("cause_frequencies cannot be empty")
    
    for freq in cause_frequencies:
        if freq < 0:
            raise ValueError("All frequencies must be non-negative")
    
    if target_cumulative_percentage < 0 or target_cumulative_percentage > 100:
        raise ValueError("target_cumulative_percentage must be between 0 and 100")
    
    total_occurrences = sum(cause_frequencies)
    if total_occurrences == 0:
        raise ValueError("Total occurrences cannot be zero; all frequencies are zero")
    
    # Create a list of (frequency, original_index) and sort by frequency descending
    indexed_freq = [(freq, i) for i, freq in enumerate(cause_frequencies)]
    sorted_indexed_freq = sorted(indexed_freq, key=lambda x: x[0], reverse=True)
    
    # Compute cumulative sum and percentages
    cumulative_sum = 0
    vital_indices = []
    for freq, original_index in sorted_indexed_freq:
        cumulative_sum += freq
        cum_pct = (cumulative_sum / total_occurrences) * 100
        vital_indices.append(original_index)
        if cum_pct >= target_cumulative_percentage:
            break
    
    return OutputSchema(vital_causes_indices=vital_indices)