import re
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    question_text: str = Field(default="", description="The text of the multiple choice question.")
    correct_answer_reasoning: str = Field(default="", description="The reasoning or explanation for the correct answer.")
    apics_definitions: Dict[str, str] = Field(default_factory=dict, description="A dictionary mapping APICS terms to their definitions.")


class OutputSchema(BaseModel):
    model_config = ConfigDict(strict=True)
    
    validation_status: str = Field(default="", description="'valid' if reasoning contains APICS terms, 'invalid' otherwise.")
    matched_terms: List[str] = Field(default_factory=list, description="Sorted list of APICS terms found in the reasoning.")
    missing_terms: List[str] = Field(default_factory=list, description="Sorted list of APICS terms not found in the reasoning.")
    feedback: str = Field(default="", description="Human-readable feedback on the validation.")


def validate_scm_reasoning(input_data: InputSchema) -> OutputSchema:
    """
    Validate reasoning for SCM multiple choice questions against APICS definitions.
    
    WHEN TO USE THIS SKILL:
    Use this skill when you need to evaluate or enhance explanations for supply chain management questions to ensure alignment with standard APICS terminology and definitions. This is ideal for certification training systems, educational quizzes, automated feedback generators, or any context where verifying the accuracy of SCM reasoning is required. It helps in assessing training effectiveness, providing corrective feedback, and maintaining consistency in SCM concept explanations.
    
    Inputs:
    - question_text (str): The text of the multiple choice question.
    - correct_answer_reasoning (str): The reasoning or explanation for the correct answer.
    - apics_definitions (Dict[str, str]): A dictionary mapping APICS terms (keys) to their definitions (values).
    
    Output:
    A dictionary with keys:
    - 'validation_status' (str): 'valid' if reasoning contains APICS terms, 'invalid' otherwise.
    - 'matched_terms' (List[str]): Sorted list of APICS terms found in the reasoning.
    - 'missing_terms' (List[str]): Sorted list of APICS terms not found in the reasoning.
    - 'feedback' (str): Human-readable feedback on the validation.
    """
    # Input validation
    if not isinstance(input_data.question_text, str) or not input_data.question_text.strip():
        raise ValueError("question_text must be a non-empty string.")
    if not isinstance(input_data.correct_answer_reasoning, str) or not input_data.correct_answer_reasoning.strip():
        raise ValueError("correct_answer_reasoning must be a non-empty string.")
    if not isinstance(input_data.apics_definitions, dict) or not input_data.apics_definitions:
        raise ValueError("apics_definitions must be a non-empty dictionary with string keys and values.")
    
    # Validate dictionary entries
    for key, value in input_data.apics_definitions.items():
        if not isinstance(key, str) or not isinstance(value, str) or not key.strip() or not value.strip():
            raise ValueError("All keys and values in apics_definitions must be non-empty strings.")
    
    # Find matched and missing terms
    matched_terms: List[str] = []
    reasoning_lower = input_data.correct_answer_reasoning.lower()
    
    for term in input_data.apics_definitions.keys():
        # Use regex with word boundaries for whole-word matching
        pattern = r'\b' + re.escape(term.lower()) + r'\b'
        if re.search(pattern, reasoning_lower):
            matched_terms.append(term)
    
    matched_terms.sort()
    missing_terms = sorted([term for term in input_data.apics_definitions.keys() if term not in matched_terms])
    
    # Determine validation status and feedback
    if matched_terms:
        validation_status = 'valid'
        feedback = f"The reasoning correctly references APICS terms: {', '.join(matched_terms)}."
    else:
        validation_status = 'invalid'
        feedback = "The reasoning does not reference any APICS terms from the provided definitions. Consider incorporating standard terminology for clarity."
    
    return OutputSchema(
        validation_status=validation_status,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
        feedback=feedback
    )