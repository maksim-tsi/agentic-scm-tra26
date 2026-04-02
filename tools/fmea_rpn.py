import pydantic
from pydantic import BaseModel, ConfigDict

class Input(BaseModel):
    model_config = ConfigDict(strict=True)
    severity_rating: int | None = None
    occurrence_rating: int | None = None
    detection_rating: int | None = None

class Output(BaseModel):
    model_config = ConfigDict(strict=True)
    rpn: int | None = None

def calculate_rpn(input_data: Input) -> Output:
    """
    Calculate the Risk Priority Number (RPN) for a failure mode in an FMEA review.

    WHEN TO USE THIS SKILL:
    This skill is used in Failure Mode and Effects Analysis (FMEA) to prioritize failure modes based on risk. It quantifies the risk by considering the severity of the failure consequence, the likelihood of occurrence, and the difficulty of detection. Use this skill when you need to assess and rank risks in product or process design, maintenance planning, or quality control to focus mitigation efforts on the most critical issues.

    Inputs:
    - input_data (Input): An object containing severity_rating, occurrence_rating, and detection_rating, each integers from 1 to 10.

    Output:
    - Output: An object containing the calculated rpn as an integer.
    """
    # Input validation
    if input_data.severity_rating is None:
        raise ValueError("severity_rating must be provided")
    if not (1 <= input_data.severity_rating <= 10):
        raise ValueError(f"severity_rating must be between 1 and 10, got {input_data.severity_rating}")
    if input_data.occurrence_rating is None:
        raise ValueError("occurrence_rating must be provided")
    if not (1 <= input_data.occurrence_rating <= 10):
        raise ValueError(f"occurrence_rating must be between 1 and 10, got {input_data.occurrence_rating}")
    if input_data.detection_rating is None:
        raise ValueError("detection_rating must be provided")
    if not (1 <= input_data.detection_rating <= 10):
        raise ValueError(f"detection_rating must be between 1 and 10, got {input_data.detection_rating}")
    
    # Calculate RPN
    rpn_value = input_data.severity_rating * input_data.occurrence_rating * input_data.detection_rating
    return Output(rpn=rpn_value)