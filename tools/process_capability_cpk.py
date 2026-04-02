from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    upper_specification_limit: Optional[float] = Field(default=None)
    lower_specification_limit: Optional[float] = Field(default=None)
    process_mean: Optional[float] = Field(default=None)
    estimated_std_dev: Optional[float] = Field(default=None)


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    cpu: Optional[float] = Field(default=0.0)
    cpl: Optional[float] = Field(default=0.0)
    cpk: Optional[float] = Field(default=0.0)


def calculate_process_capability_indices(data: InputSchema) -> OutputSchema:
    """
    Calculate process capability indices (Cpu, Cpl, Cpk) to assess if a stable process
    consistently produces items within specification limits based on short-term variation.

    WHEN TO USE THIS SKILL:
    - Quality control and manufacturing contexts to evaluate process capability
    - Determine if a process meets customer specifications and reduces defects
    - Applicable in Six Sigma projects, statistical process control (SPC), and continuous improvement
    - Use when you have process mean, standard deviation, and specification limits
    - Supports quality management decisions and process optimization initiatives

    Inputs:
    - upper_specification_limit: The upper specification limit for the process output
    - lower_specification_limit: The lower specification limit for the process output
    - process_mean: The mean of the process output from recent data
    - estimated_std_dev: The estimated standard deviation from short-term variation

    Output:
    - OutputSchema containing cpu, cpl, and cpk as floats
    """
    # Input validation
    if data.upper_specification_limit is None:
        raise ValueError("upper_specification_limit is required and cannot be None.")
    if data.lower_specification_limit is None:
        raise ValueError("lower_specification_limit is required and cannot be None.")
    if data.process_mean is None:
        raise ValueError("process_mean is required and cannot be None.")
    if data.estimated_std_dev is None:
        raise ValueError("estimated_std_dev is required and cannot be None.")

    # Validate ranges
    if data.estimated_std_dev <= 0:
        raise ValueError("estimated_std_dev must be positive to avoid division by zero.")
    if data.upper_specification_limit <= data.lower_specification_limit:
        raise ValueError("upper_specification_limit must be greater than lower_specification_limit.")

    # Calculate indices
    cpu = (data.upper_specification_limit - data.process_mean) / (3 * data.estimated_std_dev)
    cpl = (data.process_mean - data.lower_specification_limit) / (3 * data.estimated_std_dev)
    cpk = min(cpu, cpl)

    return OutputSchema(cpu=cpu, cpl=cpl, cpk=cpk)