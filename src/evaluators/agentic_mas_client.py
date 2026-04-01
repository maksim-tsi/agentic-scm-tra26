from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from evaluators.base import BaseEvaluator, EvalResult


@dataclass(frozen=True)
class AgentEndpointConfig:
    url: str
    api_key: str | None = None
    timeout_s: float = 60.0

    @classmethod
    def from_env(cls) -> "AgentEndpointConfig":
        url = os.getenv("YAAM_AGENT_URL")
        if not url:
            raise RuntimeError("Missing required env var: YAAM_AGENT_URL")

        api_key = os.getenv("YAAM_AGENT_API_KEY") or None
        timeout_s_raw = os.getenv("YAAM_AGENT_TIMEOUT_S") or "60"
        try:
            timeout_s = float(timeout_s_raw)
        except ValueError as exc:  # pragma: no cover
            raise RuntimeError("YAAM_AGENT_TIMEOUT_S must be a number") from exc

        return cls(url=url, api_key=api_key, timeout_s=timeout_s)


class AgenticMASClient:
    """
    Minimal JSON-over-HTTP client for the YAAM-based agent.

    TODO:
    - Define the DTR request/response schema (payload fields, trace IDs, artifact links)
    - Standardize error mapping into `EvalResult`
    """

    def __init__(self, config: AgentEndpointConfig):
        self._config = config

    def call(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        req = urllib.request.Request(self._config.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self._config.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Agent HTTP error: {exc.code} {exc.reason}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Agent connection error: {exc.reason}") from exc

        if not raw.strip():
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Agent returned non-JSON response: {raw[:2000]}") from exc


class AgenticMASEvaluator(BaseEvaluator):
    """
    Stub evaluator for the agentic MAS target.

    TODO:
    - Define the DTR wire format and how to send `task_id` + task payload
    - Parse the agent response and compute metrics
    """

    def __init__(self, client: AgenticMASClient, *, target: str = "agentic_mas"):
        self._client = client
        self._target = target

    def evaluate(self, task_id: str) -> EvalResult:
        raise NotImplementedError("DTR schema and scoring not implemented yet.")

