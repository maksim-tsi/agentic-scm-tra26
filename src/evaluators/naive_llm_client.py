from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

from evaluators.base import BaseEvaluator, EvalResult


DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class OpenRouterConfig:
    api_key: str
    base_url: str = DEFAULT_OPENROUTER_BASE_URL
    model: str | None = None
    app_title: str = "scm-mas-eval"
    http_referer: str | None = None

    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("Missing required env var: OPENROUTER_API_KEY")

        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL,
            model=os.getenv("OPENROUTER_MODEL") or None,
            app_title=os.getenv("OPENROUTER_APP_TITLE") or "scm-mas-eval",
            http_referer=os.getenv("OPENROUTER_HTTP_REFERER") or None,
        )


class NaiveLLMClient:
    """
    Minimal OpenRouter client wrapper.

    Notes:
    - OpenRouter exposes an OpenAI-compatible API surface.
    - This file intentionally does NOT define benchmark loading/scoring logic.
    """

    def __init__(self, config: OpenRouterConfig):
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError("Missing dependency: openai. Install with: pip install -r requirements.txt")

        self._config = config

        default_headers: dict[str, str] = {"X-Title": config.app_title}
        if config.http_referer:
            default_headers["HTTP-Referer"] = config.http_referer

        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url, default_headers=default_headers)

    def chat_completions(self, *, messages: list[dict[str, str]], model: str | None = None, **kwargs: Any) -> str:
        resolved_model = model or self._config.model
        if not resolved_model:
            raise RuntimeError("Model not set. Provide OPENROUTER_MODEL or pass model=... explicitly.")

        resp = self._client.chat.completions.create(model=resolved_model, messages=messages, **kwargs)
        content = resp.choices[0].message.content
        return content or ""


class NaiveLLMEvaluator(BaseEvaluator):
    """
    Stub evaluator for the naive OpenRouter baseline.

    TODO:
    - Load task by `task_id` from `data/benchmark/`
    - Construct the model prompt (zero-shot)
    - Compute pass/fail + metrics and return `EvalResult`
    """

    def __init__(self, client: NaiveLLMClient, *, target: str = "openrouter_naive"):
        self._client = client
        self._target = target

    def evaluate(self, task_id: str) -> EvalResult:
        raise NotImplementedError("Benchmark loading and scoring not implemented yet.")
