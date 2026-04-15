import os
import sys

import httpx
import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


def test_yaam_client_swallow_connection_error(capsys: pytest.CaptureFixture[str]) -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    out = client.store_l2_fact(
        session_id="s",
        agent_id="a",
        task_id="t",
        content="fact",
        traceparent="00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    )
    assert out is None

    captured = capsys.readouterr()
    assert "WARNING:" in captured.err


@pytest.mark.parametrize("status_code", [501, 502])
def test_yaam_client_swallow_501_502(
    status_code: int, capsys: pytest.CaptureFixture[str]
) -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, request=request, json={"error": "backend unavailable"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    out = client.query_l3_semantic(session_id="s", agent_id="a", nl_query="q", traceparent="tp")
    assert out == []

    captured = capsys.readouterr()
    assert f"YAAM {status_code}" in captured.err


def test_yaam_client_raises_on_422_contract_mismatch() -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=422, request=request, json={"detail": "schema mismatch"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    with pytest.raises(RuntimeError):
        client.assimilate_l3_knowledge(session_id="s", agent_id="a", text_to_assimilate="x", traceparent="tp")


def test_yaam_client_propagates_traceparent_header() -> None:
    _ensure_src_on_path()
    from memory.yaam_client import YaamSemanticClient

    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["traceparent"] = request.headers.get("traceparent", "")
        return httpx.Response(status_code=200, request=request, json=[])

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="http://yaam.test", transport=transport)
    client = YaamSemanticClient(gateway_url="http://yaam.test", http_client=http_client)

    traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    _ = client.query_l3_semantic(session_id="s", agent_id="a", nl_query="q", traceparent=traceparent)
    assert seen["traceparent"] == traceparent

