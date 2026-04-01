from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class EvalResult(BaseModel):
    task_id: str
    target: str
    passed: bool

    raw_output: str | None = None
    error: str | None = None

    metrics: dict[str, float | int | str] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, task_id: str) -> EvalResult:  # pragma: no cover
        raise NotImplementedError

