from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from typing import List, Union, Optional


class InputSchema(BaseModel):
    """Input schema for EDD job selection."""
    model_config = ConfigDict(strict=True, extra='forbid')
    
    jobs: Optional[List[Union[str, int]]] = None
    due_dates: Optional[List[float]] = None
    
    @field_validator('due_dates')
    @classmethod
    def validate_due_dates(cls, v: Optional[List[float]]) -> Optional[List[float]]:
        if v is None:
            return v
        for due_date in v:
            if due_date < 0:
                raise ValueError("Due dates must be non-negative.")
        return v
    
    @model_validator(mode='after')
    def validate_lists_match(self) -> 'InputSchema':
        if self.jobs is None or self.due_dates is None:
            return self
        if len(self.jobs) != len(self.due_dates):
            raise ValueError("Jobs list and due dates list must have the same length.")
        return self


class OutputSchema(BaseModel):
    """Output schema for EDD job selection."""
    model_config = ConfigDict(strict=True, extra='forbid')
    
    selected_job: Optional[Union[str, int]] = None
    earliest_due_date: Optional[float] = None
    selection_index: Optional[int] = None


def select_edd_job(jobs: List[Union[str, int]], due_dates: List[float]) -> OutputSchema:
    """
    WHEN TO USE THIS SKILL:
    This skill implements the Earliest Due Date (EDD) dispatching rule for job scheduling.
    Use it in manufacturing, service operations, or project management contexts where jobs
    must be prioritized based on due dates to minimize tardiness and improve on-time delivery.
    It selects the job with the earliest (minimum) due date from a list of jobs.
    Ideal for: production scheduling, task prioritization, dispatching systems,
    and any scenario requiring due-date-based job sequencing.
    
    Inputs:
    - jobs: List of job identifiers (strings or integers)
    - due_dates: List of corresponding due dates (numeric values, must be non-negative)
    
    Output:
    - OutputSchema containing:
        - selected_job: The job identifier with earliest due date
        - earliest_due_date: The minimum due date value found
        - selection_index: Index position of selected job
    """
    # Explicit input validation
    if not jobs:
        raise ValueError("Jobs list must not be empty.")
    if not due_dates:
        raise ValueError("Due dates list must not be empty.")
    if len(jobs) != len(due_dates):
        raise ValueError("Jobs list and due dates list must have the same length.")
    
    # Validate each due date
    for i, due_date in enumerate(due_dates):
        if not isinstance(due_date, (int, float)):
            raise ValueError(f"Due date at index {i} must be numeric, got {type(due_date)}.")
        if due_date < 0:
            raise ValueError(f"Due date at index {i} must be non-negative, got {due_date}.")
    
    # Find job with minimum due date
    min_due_date = min(due_dates)
    selection_index = due_dates.index(min_due_date)
    selected_job = jobs[selection_index]
    
    return OutputSchema(
        selected_job=selected_job,
        earliest_due_date=min_due_date,
        selection_index=selection_index
    )