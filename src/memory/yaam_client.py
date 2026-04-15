from __future__ import annotations

import os
import sys
from typing import Any

import httpx


class YaamSemanticClient:
    """
    Best-effort client for YAAM Semantic Gateway v2.

    Resilience contract:
    - Connection failures / request errors: warn to stderr, return None/[]
    - HTTP 501/502: warn to stderr, return None/[]
    - Other HTTP 4xx: raise RuntimeError (surface contract mismatches)
    """

    def __init__(
        self,
        *,
        gateway_url: str,
        timeout_s: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway_url = gateway_url.rstrip("/")
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(base_url=self._gateway_url, timeout=timeout_s)

    @classmethod
    def from_env(cls, *, timeout_s: float = 30.0) -> "YaamSemanticClient":
        gateway_url = os.getenv("YAAM_SEMANTIC_GATEWAY_URL") or ""
        if not gateway_url:
            raise ValueError("Missing required env var: YAAM_SEMANTIC_GATEWAY_URL")
        return cls(gateway_url=gateway_url, timeout_s=timeout_s)

    def close(self) -> None:
        if self._owns_client:
            try:
                self._client.close()
            except Exception:
                pass

    def __enter__(self) -> "YaamSemanticClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _headers(self, traceparent: str | None) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if traceparent:
            headers["traceparent"] = traceparent
        return headers

    def _warn(self, msg: str) -> None:
        print(f"WARNING: {msg}", file=sys.stderr)

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        traceparent: str | None,
        swallow_501_502: bool,
    ) -> Any | None:
        try:
            resp = self._client.post(path, json=payload, headers=self._headers(traceparent))
        except httpx.RequestError as exc:
            self._warn(f"YAAM request error {path}: {type(exc).__name__}: {exc}")
            return None

        if resp.status_code in (501, 502) and swallow_501_502:
            self._warn(f"YAAM {resp.status_code} for {path}; continuing without YAAM.")
            return None

        if 400 <= resp.status_code < 500:
            body = ""
            try:
                body = resp.text
            except Exception:
                body = ""
            raise RuntimeError(f"YAAM contract error {resp.status_code} for {path}: {body[:2000]}")

        if resp.status_code >= 500:
            body = ""
            try:
                body = resp.text
            except Exception:
                body = ""
            raise RuntimeError(f"YAAM server error {resp.status_code} for {path}: {body[:2000]}")

        if not resp.content:
            return None

        try:
            return resp.json()
        except Exception:
            return None

    def store_l2_fact(
        self,
        *,
        session_id: str,
        agent_id: str,
        task_id: str,
        content: str,
        traceparent: str | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            "session_id": session_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "action": "store",
            "content": content,
        }
        out = self._post_json(
            "/v2/memory/l2/facts",
            payload,
            traceparent=traceparent,
            swallow_501_502=True,
        )
        return out if isinstance(out, dict) else None

    def assimilate_l3_knowledge(
        self,
        *,
        session_id: str,
        agent_id: str,
        text_to_assimilate: str,
        domain_tags: list[str] | None = None,
        traceparent: str | None = None,
    ) -> dict[str, Any] | None:
        payload = {
            "session_id": session_id,
            "agent_id": agent_id,
            "text_to_assimilate": text_to_assimilate,
            "domain_tags": list(domain_tags or []),
        }
        out = self._post_json(
            "/v2/memory/l3/assimilate",
            payload,
            traceparent=traceparent,
            swallow_501_502=True,
        )
        return out if isinstance(out, dict) else None

    def query_l3_semantic(
        self,
        *,
        session_id: str,
        agent_id: str,
        nl_query: str,
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
        traceparent: str | None = None,
    ) -> list[Any]:
        payload = {
            "session_id": session_id,
            "agent_id": agent_id,
            "nl_query": nl_query,
            "top_k": int(top_k),
            "filters": dict(filters or {}),
        }
        out = self._post_json(
            "/v2/memory/l3/query",
            payload,
            traceparent=traceparent,
            swallow_501_502=True,
        )
        if out is None:
            return []
        if isinstance(out, list):
            return out
        if isinstance(out, dict) and isinstance(out.get("results"), list):
            return list(out["results"])
        return [out]

    def finalize_l4_artifact(
        self,
        *,
        session_id: str,
        agent_id: str,
        task_id: str,
        title: str,
        final_artifact: str,
        consensus_metadata: dict[str, Any] | None = None,
        traceparent: str | None = None,
    ) -> dict[str, Any] | None:
        meta = dict(consensus_metadata or {})
        meta.setdefault("agent_id", agent_id)

        payload = {
            "task_id": task_id,
            "session_id": session_id,
            "title": title,
            "final_artifact": final_artifact,
            "consensus_metadata": meta,
        }
        out = self._post_json(
            "/v2/memory/l4/finalize",
            payload,
            traceparent=traceparent,
            swallow_501_502=True,
        )
        return out if isinstance(out, dict) else None

